import shutil
import time
from collections import OrderedDict

import polars as pl
from polars.exceptions import SchemaError

from ._contract import ContractMixin
from .config import *


class StateMixin(ContractMixin):

    def state_cache(self, data_df_update, aggregate_func=None, key_columns=None):
        """
        Merge incoming data against a persisted snapshot and return the change set.

        Loads the previous run's `current` snapshot from disk, merges `data_df_update` into it
        (deduplicating by key columns, keeping the latest value), then computes which rows changed.

        Parameters:
            data_df_update:     Incoming rows to merge. The first column must be named "Date" (pl.Date).
            aggregate_func: Optional transform applied to data both before the merge (on the incoming update)
                            and after (on the merged result). Typically used to forward-fill sparse time-series
                            rows, derive change metrics (e.g. N-day price changes), and round values into
                            committed form ready for downstream consumers.
            key_columns:        Columns used to identify unique rows; defaults to ["Date"].

        Returns (delta, current, previous):
            delta:    Rows whose values changed between previous and current (new or modified rows).
            current:  Full dataset after merging the update into the prior snapshot, persisted to disk.
            previous: Full dataset from the prior run before this update was applied.

        Files written to disk (local_cache):
            _update:   Filtered and aggregated form of data_df_update; the rows applied this run.
            _current:  Updated current snapshot (becomes _previous on the next run).
            _previous: Current snapshot from the prior run, moved here before _current is rewritten.
            _delta:    Rows from _current that differ from _previous.
        """

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
        aggregate_function_wrapped = (lambda _data_df: _data_df) if aggregate_func is None \
            else (lambda _data_df: aggregate_func(_data_df) if len(_data_df) > 0 else _data_df)
        file_delta = abspath(f"{self.local_cache}/__{self.name.lower()}_delta.csv")
        file_update = abspath(f"{self.local_cache}/__{self.name.lower()}_update.csv")
        file_current = abspath(f"{self.local_cache}/__{self.name.lower()}_current.csv")
        file_previous = abspath(f"{self.local_cache}/__{self.name.lower()}_previous.csv")
        if not isdir(self.local_cache):
            os.makedirs(self.local_cache)
        if config.force_reprocessing:
            if isfile(file_current):
                os.remove(file_current)
        if len(data_df_update.columns) == 0 or data_df_update.columns[0] != "Date" or data_df_update.dtypes[0] != pl.Date:
            data_update_col_0 = data_df_update.columns[0] if len(data_df_update.columns) > 0 else None
            data_update_dtype_0 = self.dataframe_type_to_str(data_df_update.dtypes[0]) \
                if len(data_df_update.dtypes) > 0 else None
            raise SchemaError(f"DataFrame requires first column of parameter [data_df_update] to be named [Date] and of type [date], "
                              f"found [{data_update_col_0}] with type found [{data_update_dtype_0}]")
        data_df_update = data_df_update.filter(pl.col("Date").is_not_null())
        if len(data_df_update) == 0 and not isfile(file_current):
            data_df_update = aggregate_function_wrapped(data_df_update)
            self.print_log("DataFrame [State_Caches] skipped (no update and no current)", started=started_time)
            return data_df_update, data_df_update, data_df_update
        data_df_update = aggregate_function_wrapped(data_df_update)
        data_df_current = self.csv_read(file_current) \
            if isfile(file_current) else self.dataframe_new(schema=data_df_update.schema, print_label=f"{self.name.title()}_Current")
        data_schema_update_column_count = len(data_df_update.columns)
        update_original_columns = set(data_df_update.columns)
        data_schema = OrderedDict()
        for (data_column, data_type) in zip(data_df_update.columns, data_df_update.dtypes):
            data_schema[data_column] = data_type
        for (data_column, data_type) in zip(data_df_current.columns, data_df_current.dtypes):
            if data_column not in data_schema:
                data_schema[data_column] = data_type
                data_df_update = data_df_update.with_columns(
                    pl.lit(None).cast(data_schema[data_column]).alias(data_column))
        state_key_columns = _resolve_key_columns(data_schema.keys())
        data_df_update = data_df_update.select(data_schema.keys()).with_columns(pl.col("Date").cast(pl.Date)).unique(
            subset=state_key_columns, keep="last").sort(state_key_columns).with_columns(pl.lit(True).alias("__in_update"))
        for data_column in data_schema:
            if data_column not in data_df_current:
                data_df_current = data_df_current.with_columns(
                    pl.lit(None).cast(data_schema[data_column]).alias(data_column))
            elif data_df_current.schema[data_column] != data_schema[data_column]:
                data_df_current = data_df_current.with_columns(
                    pl.col(data_column).cast(data_schema[data_column], strict=False))
        data_df_current = data_df_current.select(data_schema.keys()).with_columns(pl.col("Date").cast(pl.Date)).sort(state_key_columns)
        self.csv_write(data_df_update.drop("__in_update"), file_update)
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
        data_df_previous_value_columns = [c for c in data_df_previous.columns if c not in state_key_columns]
        self.add_counter(CTR_SRC_DATA, CTR_ACT_PREVIOUS_COLUMNS, len(data_df_previous.columns) - len(state_key_columns))
        self.add_counter(CTR_SRC_DATA, CTR_ACT_PREVIOUS_ROWS, len(data_df_previous.filter(
            pl.any_horizontal([pl.col(c).is_not_null() for c in data_df_previous_value_columns])) if data_df_previous_value_columns else data_df_previous))
        value_columns = [c for c in data_schema.keys() if c not in state_key_columns]
        coalesce_cols = [c for c in value_columns if c in update_original_columns]
        overwrite_cols = [c for c in value_columns if c not in update_original_columns]
        merge_exprs = [pl.coalesce([f"{c}_upd", c]).alias(c) for c in coalesce_cols] + \
                      [pl.when(pl.col("__in_update").is_not_null()).then(pl.col(f"{c}_upd")).otherwise(pl.col(c)).alias(c) for c in overwrite_cols]
        data_df_current = (
            data_df_current.lazy()
            .join(data_df_update.lazy(), on=state_key_columns, how="full", coalesce=True, suffix="_upd")
            .with_columns(merge_exprs)
            .select(list(data_schema.keys()))
            .sort(state_key_columns)
            .collect()
        )
        data_df_current = aggregate_function_wrapped(data_df_current)
        for data_column, data_type in zip(data_df_current.columns, data_df_current.dtypes):
            if data_column in data_df_previous.columns and data_df_previous.schema[data_column] != data_type:
                data_df_previous = data_df_previous.with_columns(
                    pl.col(data_column).cast(data_type, strict=False))
        for data_column, data_type in data_schema.items():
            if data_column not in data_df_current.columns:
                data_df_current = data_df_current.with_columns(
                    pl.lit(None).cast(data_type).alias(data_column))
        data_df_current = data_df_current.select(data_schema.keys())
        self.csv_write(data_df_current, file_current)
        data_df_current_value_columns = [c for c in data_df_current.columns if c not in state_key_columns]
        self.add_counter(CTR_SRC_DATA, CTR_ACT_CURRENT_COLUMNS, len(data_df_current.columns) - len(state_key_columns))
        self.add_counter(CTR_SRC_DATA, CTR_ACT_CURRENT_ROWS, len(data_df_current.filter(
            pl.any_horizontal([pl.col(c).is_not_null() for c in data_df_current_value_columns])) if data_df_current_value_columns else data_df_current))
        data_df_delta = pl.concat([data_df_previous, data_df_current]).select(data_schema.keys())
        data_df_delta = data_df_delta.filter(data_df_delta.is_duplicated().not_()).unique(subset=state_key_columns, keep="last").sort(state_key_columns)
        self.csv_write(data_df_delta, file_delta)
        self.add_counter(CTR_SRC_DATA, CTR_ACT_DELTA_COLUMNS, len(data_schema) - len(state_key_columns) if data_schema_update_column_count > len(state_key_columns) else 0)
        self.add_counter(CTR_SRC_DATA, CTR_ACT_DELTA_ROWS, len(data_df_delta))
        self.print_log("DataFrame [State_Caches] created", started=started_time)
        return data_df_delta.sort(state_key_columns), data_df_current.sort(state_key_columns), data_df_previous.sort(state_key_columns)
