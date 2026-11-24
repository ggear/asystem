import time
from os.path import splitext

import polars as pl
import polars.selectors as cs
from python_calamine import CalamineWorkbook

from ._contract import ContractMixin
from .config import *
from .logger import dataframe_print

_EXCEL_NA = frozenset(["", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan", "1.#IND", "1.#QNAN", "<NA>", "N/A", "NA", "NULL", "NaN", "None", "n/a", "nan", "null"])


class DataFramesMixin(ContractMixin):
    def excel_read(
        self,
        local_path,
        schema=None,
        skip_rows=0,
        na_values=None,
        print_rows=PL_PRINT_ROWS,
    ):
        started_time = time.time()
        local_path = str(local_path).lower()
        if schema is None:
            schema = {}
        if na_values is None:
            na_values = []
        effective_na = _EXCEL_NA | set(na_values)
        workbook = CalamineWorkbook.from_path(local_path)
        raw_rows = list(workbook.get_sheet_by_index(0).iter_rows())[skip_rows:]
        rows = [[None if (isinstance(value, str) and value in effective_na) else value for value in row] for row in raw_rows]
        if rows:
            headers = [value if isinstance(value, str) else f"column_{i}" for i, value in enumerate(rows[0])]
            rows = rows[1:]
        else:
            headers = []
        column_data = {headers[i]: [row[i] if i < len(row) else None for row in rows] for i in range(len(headers))} if rows else {header: [] for header in headers}
        data_df = pl.DataFrame(column_data, nan_to_null=True)
        if schema:
            data_df = data_df.with_columns([pl.col(column).cast(dtype) for column, dtype in schema.items() if column in data_df.columns])
        data_df = data_df.select([column for column in data_df.columns if data_df[column].null_count() < len(data_df)])
        data_df = data_df.filter(~pl.all_horizontal(pl.all().is_null()))
        data_df = data_df.with_columns(cs.float().round(6))
        return dataframe_print(
            self.name,
            data_df,
            print_label=splitext(basename(local_path))[0].removeprefix("__").removeprefix("_"),
            print_suffix=f"from [{local_path}]",
            print_rows=print_rows,
            started=started_time,
        )

    def csv_write(self, data_df, local_path, print_prefix="File", print_label=None, print_verb="written", print_rows=PL_PRINT_ROWS, started=None, float_precision=None):
        started_time = time.time() if started is None else started
        local_path = str(local_path).lower()
        data_df.write_csv(local_path, line_terminator="\n", float_precision=float_precision)
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

    def csv_read(self, local_path, schema=None, print_label=None, print_verb="loaded", print_rows=PL_PRINT_ROWS):
        started_time = time.time()
        local_path = str(local_path).lower()
        if schema is None:
            schema = {}
        typed = len(schema) > 0 and set(pl.read_csv(local_path, n_rows=0, raise_if_empty=False).columns) <= set(schema)
        data_df = pl.read_csv(
            local_path,
            schema_overrides=schema if len(schema) > 0 else None,
            try_parse_dates=not typed,
            raise_if_empty=False,
            infer_schema=not typed,
            infer_schema_length=None,
        )
        return dataframe_print(
            self.name,
            data_df,
            print_label=print_label or splitext(basename(local_path))[0].removeprefix("__").removeprefix("_"),
            print_verb=print_verb,
            print_suffix=f"from [{local_path}]",
            print_rows=print_rows,
            started=started_time,
        )

    def dataframe_new(self, data=None, schema=None, orient=None, print_label=None, print_suffix=None, print_compact=False, print_rows=PL_PRINT_ROWS, started=None):
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
            dataframe_print(self.name, data_df, compact=print_compact, print_label=print_label, print_suffix=print_suffix, print_rows=print_rows, started=started_time)
        return data_df

    def dataframe_type_to_str(self, data_type):
        return str(data_type)
