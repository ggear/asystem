import time
from os.path import splitext

import polars as pl
import polars.selectors as cs

from . import database as _database
from ._contract import ContractMixin
from .config import *


class DataFramesMixin(ContractMixin):

    def excel_read(self, local_path, schema=None, sheet_name=0, header_rows=0, skip_rows=0,
                   na_values=None, drop_na_cols=True, drop_na_rows=True, float_round_places=6,
                   print_label=None, print_rows=PL_PRINT_ROWS):
        import pandas as pd
        started_time = time.time()
        if schema is None:
            schema = {}
        if na_values is None:
            na_values = []
        data_df_pd = pd.read_excel(local_path, sheet_name=sheet_name, header=header_rows, skiprows=skip_rows, na_values=na_values)
        if drop_na_cols:
            data_df_pd = data_df_pd.dropna(axis=1, how="all")
        if drop_na_rows:
            data_df_pd = data_df_pd.dropna(axis=0, how="all")
        data_df = pl.from_pandas(data_df_pd, schema_overrides=schema if len(schema) > 0 else None).with_columns(cs.float().round(float_round_places))
        return self.dataframe_print(
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
        data_df.write_csv(local_path)
        return self.dataframe_print(
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
        if schema is None:
            schema = {}
        data_df = pl.read_csv(local_path, schema_overrides=schema if len(schema) > 0 else None,
                              try_parse_dates=True, raise_if_empty=False, infer_schema_length=None)
        return self.dataframe_print(
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
            self.dataframe_print(
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
        line_expressions = [pl.lit(self.name.lower() + "," + ",".join([f"{tag}={tags[tag]}" for tag in tags]) + " ")]
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
        self.dataframe_print(
            data_df,
            print_label=print_label,
            print_verb="serialised",
            print_suffix=f"to [{emitted:,}] lines",
            started=started_time,
        )
        self.add_counter(CTR_SRC_EGRESS, CTR_ACT_DATABASE_COLUMNS, len(data_df.columns))
        self.add_counter(CTR_SRC_EGRESS, CTR_ACT_DATABASE_ROWS, total_rows)

    def database_upload(self, data_df, tags=None,
                        print_label=None, chunk_rows=5000):
        if len(data_df.columns) <= 1 or len(data_df) == 0:
            return
        if config.disable_uploads or _database.database_client is None:
            for _ in self.dataframe_to_lineprotocol(data_df, tags=tags, print_label=print_label, chunk_rows=chunk_rows):
                pass
            if config.disable_uploads:
                tags_used = {k: v for k, v in (tags or {}).items() if k != "source"}
                tag_suffix = f" [{','.join(f'{k}={v}' for k, v in tags_used.items())}]" if tags_used else ""
                csv_path = abspath(f"{self.local_cache}/_Database_{self.name}.csv")
                date_col = data_df.columns[0]
                fmt = '%Y-%m-%d' if data_df.dtypes[0] == pl.Date else '%Y-%m-%d %H:%M:%S'
                csv_df = data_df \
                    .rename({col: f"{col}{tag_suffix}" for col in data_df.columns[1:]}) \
                    .with_columns(pl.col(date_col).cast(pl.Datetime).dt.strftime(fmt).alias(date_col))
                if csv_path in self._db_cache_dfs:
                    csv_df = self._db_cache_dfs[csv_path].join(csv_df, on=date_col, how="full", coalesce=True).sort(date_col)
                self._db_cache_dfs[csv_path] = csv_df
            return
        try:
            buffer = []
            for line in self.dataframe_to_lineprotocol(data_df, tags=tags, print_label=print_label, chunk_rows=chunk_rows):
                buffer.append(line)
                if len(buffer) >= chunk_rows:
                    _database.database_client.write(record=buffer, write_precision="ms")
                    buffer = []
            if buffer:
                _database.database_client.write(record=buffer, write_precision="ms")
        except Exception as exception:
            self.print_log(
                f"DataFrame{'' if print_label is None else f' [{print_label}]'} write failed",
                exception=exception,
            )
            self.add_counter(CTR_SRC_EGRESS, CTR_ACT_ERRORED)

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

    def dataframe_print(self, data_df, messages=None, compact=False,
                        print_prefix="DataFrame", print_label=None, print_verb="created", print_suffix=None, print_rows=PL_PRINT_ROWS, started=None):
        if print_rows < 0:
            return data_df
        if messages is None:
            label = f" [{print_label}]" if print_label else ""
            suffix = f" {print_suffix}" if print_suffix else ""
            messages = (
                f"{print_prefix}{label} {print_verb} "
                f"with [{len(data_df.columns):,}] columns "
                f"and [{len(data_df):,}] rows{suffix}"
            )
        self.print_log(
            messages,
            None if print_rows == 0 else self.dataframe_to_str(data_df, compact, print_rows),
            started=started,
            level="debug",
        )
        return data_df
