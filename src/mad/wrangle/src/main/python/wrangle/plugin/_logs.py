import time
from datetime import timedelta
from os.path import abspath, isfile

import polars as pl

from ._contract import ContractMixin
from .config import LOG_KIND_ERROR, LOG_KIND_INFO, LOG_KIND_WARNING, LOG_RECORD_DAYS, LOG_SCHEMA, LOG_STATE_CURRENT, LOG_STATE_HISTORIC
from .counters import CTR_ACT_ERRORED, CTR_SRC_SOURCES
from .logger import dataframe_print


class LogsMixin(ContractMixin):
    def error(self, errors, tab, key, code, detail):
        kind, _, _, counter = self.error_codes[code]
        if kind == LOG_KIND_ERROR and (counter != CTR_SRC_SOURCES or not any(error["Counter"] == counter and error["Tab"] == tab and error["Code"] == code for error in errors)):
            self.add_counter(counter, CTR_ACT_ERRORED)
        raised = self.now()
        errors.append(
            {
                "Date": raised.date(),
                "Time": raised.strftime("%H:%M:%S"),
                "Date Raised": raised.date(),
                "Kind": kind,
                "State": LOG_STATE_CURRENT,
                "Counter": counter,
                "Tab": tab,
                "Key": key,
                "Code": code,
                "Detail": detail,
            }
        )
        self.print_log(f"{self.name} {kind.lower()} [{code}] tab [{tab}] key [{key}] {detail}", level={LOG_KIND_ERROR: "error", LOG_KIND_WARNING: "warn"}.get(kind, "info"))

    def logs_merged(self, errors, today):
        started_time = time.time()
        logs_file = abspath(f"{self.local_cache}/__{self.name.lower()}_logs.csv")
        prior_df = self.csv_read(logs_file, schema=LOG_SCHEMA, print_rows=0) if isfile(logs_file) else pl.DataFrame(schema=LOG_SCHEMA)
        prior_df = (
            prior_df.with_columns([pl.lit(None, dtype=dtype).alias(column) for column, dtype in LOG_SCHEMA.items() if column not in prior_df.columns])
            .with_columns(pl.coalesce("Date Raised", "Date").alias("Date Raised"))
            .select(list(LOG_SCHEMA))
        )
        kinds = {code: kind for code, (kind, _, _, _) in self.error_codes.items()}
        standing = [code for code, (_, held, _, _) in self.error_codes.items() if held]
        kept = [code for code, (_, _, history, _) in self.error_codes.items() if history]
        identity = ["Counter", "Tab", "Key", "Code"]
        now_df = pl.DataFrame(errors, schema=LOG_SCHEMA).with_columns(pl.lit(today, dtype=pl.Date).alias("Date Raised"))
        prior_standing_df = prior_df.filter(pl.col("Code").is_in(standing))
        standing_df = (
            now_df.filter(pl.col("Code").is_in(standing))
            .unique(identity, keep="first", maintain_order=True)
            .join(
                prior_standing_df.filter(pl.col("State").fill_null(LOG_STATE_CURRENT) == LOG_STATE_CURRENT).select([*identity, pl.col("Date").alias("__first"), pl.col("Time").alias("__first_time")]),
                on=identity,
                how="left",
            )
            .with_columns(pl.when(pl.col("__first").is_not_null()).then(pl.col("__first_time")).otherwise(pl.col("Time")).alias("Time"), pl.coalesce("__first", "Date").alias("Date"))
            .select(list(LOG_SCHEMA))
        )
        resolved_df = prior_standing_df.join(standing_df.select(identity), on=identity, how="anti", nulls_equal=True).with_columns(pl.lit(LOG_STATE_HISTORIC).alias("State"))
        records_df = (
            pl.concat([prior_df.filter(~pl.col("Code").is_in(standing)), now_df.filter(~pl.col("Code").is_in(standing))])
            .unique([*identity, "Detail"], keep="first", maintain_order=True)
            .drop("State")
            .join(
                now_df.select([*identity, "Detail"]).unique().with_columns(pl.lit(LOG_STATE_CURRENT).alias("State")),
                on=[*identity, "Detail"],
                how="left",
                nulls_equal=True,
                maintain_order="left",
            )
            .with_columns(
                pl.col("State").fill_null(LOG_STATE_HISTORIC),
                pl.when(pl.col("State").is_not_null()).then(pl.lit(today, dtype=pl.Date)).otherwise(pl.col("Date Raised")).alias("Date Raised"),
            )
            .select(list(LOG_SCHEMA))
        )
        logs_df = (
            pl.concat([standing_df, resolved_df, records_df])
            .filter(pl.col("Code").is_in(list(kinds)) & ((pl.col("State") == LOG_STATE_CURRENT) | (pl.col("Code").is_in(kept) & (pl.col("Date Raised") > today - timedelta(days=LOG_RECORD_DAYS)))))
            .with_columns(pl.col("Code").replace_strict(kinds).alias("Kind"))
            .with_columns(pl.when((pl.col("State") == LOG_STATE_HISTORIC) & (pl.col("Kind") == LOG_KIND_ERROR)).then(pl.lit(LOG_KIND_WARNING)).otherwise(pl.col("Kind")).alias("Kind"))
            .with_columns(pl.col("Kind").replace_strict({LOG_KIND_ERROR: 0, LOG_KIND_WARNING: 1, LOG_KIND_INFO: 2}, default=3, return_dtype=pl.Int8).alias("__rank"))
            .sort(["__rank", "Date", "Time", "Tab", "Code", "Key"], descending=[False, True, True, False, False, False], nulls_last=True)
            .drop("__rank")
        )
        dataframe_print(self.name, logs_df, print_label="Logs", print_verb="rendered", started=started_time)
        self.csv_write(logs_df, logs_file, print_rows=0)
        return logs_df
