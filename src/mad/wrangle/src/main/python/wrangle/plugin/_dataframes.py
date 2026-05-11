import time
from os.path import splitext

import polars as pl
import polars.selectors as cs

from ._contract import ContractMixin
from .config import *
from .logger import dataframe_print

_EXCEL_NA = frozenset(['', '#N/A', '#N/A N/A', '#NA', '-1.#IND', '-1.#QNAN', '-NaN', '-nan', '1.#IND', '1.#QNAN', '<NA>', 'N/A', 'NA', 'NULL', 'NaN', 'None', 'n/a', 'nan', 'null'])


class DataFramesMixin(ContractMixin):

    def excel_read(self, local_path, schema=None, sheet_name: int | str = 0, header_rows=0, skip_rows=0,
                   na_values=None, drop_na_cols=True, drop_na_rows=True, float_round_places=6,
                   print_label=None, print_rows=PL_PRINT_ROWS):
        started_time = time.time()
        local_path = str(local_path).lower()
        if schema is None:
            schema = {}
        if na_values is None:
            na_values = []
        from python_calamine import CalamineWorkbook
        effective_na = _EXCEL_NA | set(na_values)
        wb = CalamineWorkbook.from_path(local_path)
        ws = wb.get_sheet_by_index(sheet_name) if isinstance(sheet_name, int) else wb.get_sheet_by_name(sheet_name)
        raw_rows = list(ws.iter_rows())[skip_rows:]
        rows = [[None if (isinstance(v, str) and v in effective_na) else v for v in row] for row in raw_rows]
        if header_rows is not None and len(rows) > header_rows:
            headers = [v if isinstance(v, str) else f'column_{i}' for i, v in enumerate(rows[header_rows])]
            rows = rows[header_rows + 1:]
        else:
            headers = [f'column_{i}' for i in range(len(rows[0]) if rows else 0)]
        col_data = {headers[i]: [row[i] if i < len(row) else None for row in rows] for i in range(len(headers))} if rows else {h: [] for h in headers}
        data_df = pl.DataFrame(col_data, nan_to_null=True)
        if schema:
            data_df = data_df.with_columns([pl.col(c).cast(t) for c, t in schema.items() if c in data_df.columns])
        if drop_na_cols:
            data_df = data_df.select([col for col in data_df.columns if data_df[col].null_count() < len(data_df)])
        if drop_na_rows:
            data_df = data_df.filter(~pl.all_horizontal(pl.all().is_null()))
        data_df = data_df.with_columns(cs.float().round(float_round_places))
        return dataframe_print(
            self.name,
            data_df,
            print_label=print_label or splitext(basename(local_path))[0].removeprefix("__").removeprefix("_"),
            print_suffix=f"from [{local_path}]",
            print_rows=print_rows,
            started=started_time,
        )

    def csv_write(self, data_df, local_path,
                  print_prefix="File", print_label=None, print_verb="written",
                  print_rows=PL_PRINT_ROWS, started=None):
        started_time = time.time() if started is None else started
        local_path = str(local_path).lower()
        data_df.write_csv(local_path)
        return dataframe_print(
            self.name,
            data_df,
            print_label=print_label or basename(local_path).split(".")[0].removeprefix("__").removeprefix("_"),
            print_prefix=print_prefix,
            print_verb=print_verb,
            print_suffix=f"to [{local_path}]",
            print_rows=print_rows,
            started=started_time,
        )

    def csv_read(self, local_path, schema=None,
                 print_label=None, print_verb="loaded", print_rows=PL_PRINT_ROWS):
        started_time = time.time()
        local_path = str(local_path).lower()
        if schema is None:
            schema = {}
        data_df = pl.read_csv(local_path, schema_overrides=schema if len(schema) > 0 else None,
                              try_parse_dates=True, raise_if_empty=False, infer_schema_length=None)
        return dataframe_print(
            self.name,
            data_df,
            print_label=print_label or splitext(basename(local_path))[0].removeprefix("__").removeprefix("_"),
            print_verb=print_verb,
            print_suffix=f"from [{local_path}]",
            print_rows=print_rows,
            started=started_time,
        )

    def dataframe_new(self, data=None, schema=None, orient=None,
                      print_label=None, print_suffix=None, print_compact=False, print_rows=PL_PRINT_ROWS, started=None):
        started_time = time.time() if started is None else started
        if data is None:
            data = []
        if schema is None:
            schema = {}
        data_df = pl.DataFrame(
            data=data if len(data) > 0 else None,
            schema=schema if len(schema) > 0 else None,
            orient=orient,
            nan_to_null=True,
        )
        if len(data) > 0 or len(schema) > 0:
            dataframe_print(self.name,
                            data_df,
                            compact=print_compact,
                            print_label=print_label,
                            print_suffix=print_suffix,
                            print_rows=print_rows,
                            started=started_time
                            )
        return data_df

    def dataframe_to_lineprotocol(self, data_df, tags=None,
                                  print_label=None, chunk_rows=5000):
        started_time = time.time()
        tags = dict(tags or {})
        tags["source"] = "wrangle"
        if len(data_df.columns) <= 1 or len(data_df) == 0:
            return
        if data_df.select(pl.sum_horizontal(pl.all().is_null().sum())).rows()[0][0] > 0:
            raise Exception(
                "Dataframe contains null values which should be purged before line protocol serialisation")
        renamed_columns = ["timestamp"] + [column.strip().replace(' ', '-').lower() for column in data_df.columns[1:]]
        data_df = data_df.rename(dict(zip(data_df.columns, renamed_columns))).with_columns(pl.col("timestamp").cast(pl.Datetime).dt.epoch() * 1000)
        # noinspection PyUnresolvedReferences
        database_table = self.remote_repos.database_table or self.name.lower()
        line_expressions = [pl.lit(database_table + "," + ",".join([f"{tag}={tags[tag]}" for tag in tags]) + " ")]
        for column in data_df.columns[1:]:
            if len(line_expressions) > 1:
                line_expressions.append(pl.lit(","))
            line_expressions.extend([pl.lit(f"{column}="), pl.col(column)])
        line_expressions.extend([pl.lit(" "), pl.col("timestamp")])
        total_rows = len(data_df)
        emitted = 0
        for offset in range(0, total_rows, chunk_rows):
            chunk = data_df.slice(offset, chunk_rows)
            series = chunk.lazy().select(pl.concat_str(line_expressions)).collect().to_series()
            for line in series:
                yield line
                emitted += 1
        dataframe_print(self.name,
                        data_df,
                        print_label=print_label,
                        print_verb="serialised",
                        print_suffix=f"to [{emitted:,}] lines",
                        started=started_time,
                        )
        self.add_counter(CTR_SRC_EGRESS, CTR_ACT_DATABASE_COLUMNS, len(data_df.columns))
        self.add_counter(CTR_SRC_EGRESS, CTR_ACT_DATABASE_ROWS, total_rows)

    # noinspection PyMethodMayBeStatic
    def dataframe_type_to_str(self, data_type):
        return str(data_type)

    # noinspection PyMethodMayBeStatic
    def dataframe_to_str(self, data_df, compact=True,
                         print_rows=PL_PRINT_ROWS):
        if compact:
            schema = []
            for column in data_df.schema:
                schema.append(f"{column}({str(data_df.schema[column])})")
            return "[" + ", ".join(schema) + "]"
        else:
            with pl.Config(
                    tbl_rows=print_rows,
                    tbl_cols=-1,
                    fmt_str_lengths=50,
                    set_tbl_width_chars=30000,
                    set_fmt_float="full",
                    set_ascii_tables=True,
                    tbl_formatting="ASCII_FULL_CONDENSED",
                    set_tbl_hide_dataframe_shape=True,
            ):
                data_lines = str(data_df).split('\n')
                return data_lines
