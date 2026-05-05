import shutil
import time
from collections import OrderedDict

import polars as pl
from polars.exceptions import SchemaError

from ._contract import ContractMixin
from .config import *


class StateMixin(ContractMixin):

    def state_cache(self, data_df_update, aggregate_function=None, key_columns=None):

        def _resolve_key_columns(available_columns):
            resolved = [column for column in key_columns if column in available_columns]
            if len(resolved) == 0 and "Date" in available_columns:
                resolved = ["Date"]
            missing = [column for column in key_columns if column not in available_columns]
            if len(missing) > 0:
                self.print_log(f"State cache key columns unavailable and ignored: [{', '.join(missing)}]", level="debug")
            return resolved

        started_time = time.time()
        key_columns = key_columns if key_columns is not None else ["Date"]
        aggregate_function_wrapped = (lambda _data_df: _data_df) if aggregate_function is None \
            else (lambda _data_df: aggregate_function(_data_df) if len(_data_df) > 0 else _data_df)
        file_delta = abspath(f"{self.local_cache}/__{self.name.title()}_Delta.csv")
        file_update = abspath(f"{self.local_cache}/__{self.name.title()}_Update.csv")
        file_current = abspath(f"{self.local_cache}/__{self.name.title()}_Current.csv")
        file_previous = abspath(f"{self.local_cache}/__{self.name.title()}_Previous.csv")
        if not isdir(self.local_cache):
            os.makedirs(self.local_cache)

        # TODO: Remove?
        # if not config.disable_downloads and config.force_reprocessing:
        #     if isfile(file_current):
        #         os.remove(file_current)
        if config.force_reprocessing:
            if isfile(file_current):
                os.remove(file_current)

        if len(data_df_update.columns) == 0 or data_df_update.columns[0] != "Date" or data_df_update.dtypes[0] != pl.Date:
            data_update_col_0 = data_df_update.columns[0] if len(data_df_update.columns) > 0 else None
            data_update_dtype_0 = self.dataframe_type_to_str(data_df_update.dtypes[0]) \
                if len(data_df_update.dtypes) > 0 else None
            raise SchemaError(f"DataFrame requires first column of parameter [data_df_update] to be named [Date] and of type [date], "
                              f"found [{data_update_col_0}] with type found [{data_update_dtype_0}]")

        # TODO: Remove?
        # if config.disable_downloads:
        #     data_df_current = self.csv_read(file_current) \
        #         if isfile(file_current) else self.dataframe_new(schema={"Date": pl.Date}, print_label=f"{self.name.title()}_Current")
        #     self.print_log("DataFrame [State_Caches] created ignoring updates", started=started_time)
        #     state_key_columns = _resolve_key_columns(data_df_current.columns)
        #     data_df_current = data_df_current.sort(state_key_columns)
        #     return self.dataframe_new(schema=data_df_current.schema), data_df_current, data_df_current

        data_df_update = data_df_update.filter(pl.col("Date").is_not_null())
        data_df_update = aggregate_function_wrapped(data_df_update)
        data_df_current = self.csv_read(file_current) \
            if isfile(file_current) else self.dataframe_new(schema=data_df_update.schema, print_label=f"{self.name.title()}_Current")
        data_schema_update_column_count = len(data_df_update.columns)
        data_schema = OrderedDict()
        for (data_column, data_type) in zip(data_df_update.columns, data_df_update.dtypes):
            data_schema[data_column] = data_type
        for (data_column, data_type) in zip(data_df_current.columns, data_df_current.dtypes):
            if data_column not in data_schema:
                data_schema[data_column] = data_type
                data_df_update = data_df_update.with_columns(
                    pl.lit(None).cast(data_schema[data_column]).alias(data_column))
        state_key_columns = _resolve_key_columns(data_schema.keys())
        data_df_update = data_df_update.select(data_schema.keys()).with_columns(pl.col("Date").cast(pl.Date)).sort(
            state_key_columns)
        for data_column in data_schema:
            if data_column not in data_df_current:
                data_df_current = data_df_current.with_columns(
                    pl.lit(None).cast(data_schema[data_column]).alias(data_column))
            elif data_df_current.schema[data_column] != data_schema[data_column]:
                data_df_current = data_df_current.with_columns(
                    pl.col(data_column).cast(data_schema[data_column], strict=False))
        data_df_current = data_df_current.select(data_schema.keys()).with_columns(pl.col("Date").cast(pl.Date)).sort(state_key_columns)
        self.csv_write(data_df_update, file_update)
        self.add_counter(CTR_SRC_DATA, CTR_ACT_UPDATE_COLUMNS, data_schema_update_column_count - len(state_key_columns))
        self.add_counter(CTR_SRC_DATA, CTR_ACT_UPDATE_ROWS, len(data_df_update))
        if isfile(file_current):
            shutil.move(file_current, file_previous)
        elif isfile(file_previous):
            os.remove(file_previous)
        data_df_previous = self.csv_read(file_previous) \
            if isfile(file_previous) else self.dataframe_new(schema=data_schema, print_label=f"{self.name.title()}_Previous")
        for data_column in data_schema:
            if data_column not in data_df_previous:
                data_df_previous = data_df_previous.with_columns(
                    pl.lit(None).cast(data_schema[data_column]).alias(data_column))
        data_df_previous = data_df_previous.select(data_schema.keys())
        self.add_counter(CTR_SRC_DATA, CTR_ACT_PREVIOUS_COLUMNS, len(data_df_previous.columns) - len(state_key_columns))
        self.add_counter(CTR_SRC_DATA, CTR_ACT_PREVIOUS_ROWS, len(data_df_previous))
        data_df_current = pl.concat([data_df_current, data_df_update]) \
            .select(data_schema.keys()).unique(subset=state_key_columns, keep="last").sort(state_key_columns)
        data_df_current = aggregate_function_wrapped(data_df_current)
        for data_column, data_type in zip(data_df_current.columns, data_df_current.dtypes):
            if data_column in data_df_previous.columns and data_df_previous.schema[data_column] != data_type:
                data_df_previous = data_df_previous.with_columns(
                    pl.col(data_column).cast(data_type, strict=False))
        data_df_current = data_df_current.select(data_schema.keys())
        self.csv_write(data_df_current, file_current)
        self.add_counter(CTR_SRC_DATA, CTR_ACT_CURRENT_COLUMNS, len(data_df_current.columns) - len(state_key_columns))
        self.add_counter(CTR_SRC_DATA, CTR_ACT_CURRENT_ROWS, len(data_df_current))
        data_df_delta = pl.concat([data_df_previous, data_df_current]).select(data_schema.keys())
        data_df_delta = data_df_delta.filter(data_df_delta.is_duplicated().not_()).unique(subset=state_key_columns, keep="last").sort(state_key_columns)
        self.csv_write(data_df_delta, file_delta)
        self.add_counter(CTR_SRC_DATA, CTR_ACT_DELTA_COLUMNS, len(data_schema) - len(state_key_columns) if data_schema_update_column_count > len(state_key_columns) else 0)
        self.add_counter(CTR_SRC_DATA, CTR_ACT_DELTA_ROWS, len(data_df_delta))
        self.print_log("DataFrame [State_Caches] created", started=started_time)
        return data_df_delta.sort(state_key_columns), data_df_current.sort(state_key_columns), data_df_previous.sort(state_key_columns)
