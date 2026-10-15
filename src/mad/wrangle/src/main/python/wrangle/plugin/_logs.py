import time
from datetime import timedelta
from os.path import abspath, isfile

import polars as pl

from ._contract import ContractMixin
from .config import LOG_KIND_ERROR, LOG_KIND_WARNING, LOG_RECORD_DAYS, LOG_SCHEMA
from .counters import CTR_ACT_ERRORED, CTR_SRC_SOURCES
from .logger import dataframe_print


class LogsMixin(ContractMixin):
    def error(self, errors, tab, key, code, detail):
        kind, _, counter = self.error_codes[code]
        if counter != CTR_SRC_SOURCES or not any(error["Counter"] == counter and error["Tab"] == tab and error["Code"] == code for error in errors):
            self.add_counter(counter, CTR_ACT_ERRORED)
        raised = self.now()
        errors.append({"Date": raised.date(), "Time": raised.strftime("%H:%M:%S"), "Kind": kind, "Counter": counter, "Tab": tab, "Key": key, "Code": code, "Detail": detail})
        self.print_log(f"{self.name} {kind.lower()} [{code}] tab [{tab}] key [{key}] {detail}", level={LOG_KIND_ERROR: "error", LOG_KIND_WARNING: "warn"}.get(kind, "info"))

    def logs_merged(self, errors, today):
        started_time = time.time()
        logs_file = abspath(f"{self.local_cache}/__{self.name.lower()}_logs.csv")
        prior_df = self.csv_read(logs_file, schema=LOG_SCHEMA, print_rows=0).select(list(LOG_SCHEMA)) if isfile(logs_file) else pl.DataFrame(schema=LOG_SCHEMA)
        kinds = {code: kind for code, (kind, _, _) in self.error_codes.items()}
        standing = [code for code, (_, held, _) in self.error_codes.items() if held]
        identity = ["Counter", "Tab", "Key", "Code"]
        now_df = pl.DataFrame(errors, schema=LOG_SCHEMA)
        standing_df = (
            now_df.filter(pl.col("Code").is_in(standing))
            .unique(identity, keep="first", maintain_order=True)
            .join(prior_df.filter(pl.col("Code").is_in(standing)).select([*identity, pl.col("Date").alias("__first"), pl.col("Time").alias("__first_time")]), on=identity, how="left")
            .with_columns(pl.when(pl.col("__first").is_not_null()).then(pl.col("__first_time")).otherwise(pl.col("Time")).alias("Time"), pl.coalesce("__first", "Date").alias("Date"))
            .select(list(LOG_SCHEMA))
        )
        records_df = (
            pl.concat([prior_df.filter(~pl.col("Code").is_in(standing)), now_df.filter(~pl.col("Code").is_in(standing))])
            .unique([*identity, "Detail"], keep="first", maintain_order=True)
            .filter(pl.col("Date") > today - timedelta(days=LOG_RECORD_DAYS))
        )
        logs_df = (
            pl.concat([standing_df, records_df])
            .filter(pl.col("Code").is_in(list(kinds)))
            .with_columns(pl.col("Code").replace_strict(kinds).alias("Kind"))
            .sort(["Date", "Time", "Tab", "Code", "Key"], descending=[True, True, False, False, False], nulls_last=True)
        )
        dataframe_print(self.name, logs_df, print_label="Logs", print_verb="rendered", started=started_time)
        self.csv_write(logs_df, logs_file, print_rows=0)
        return logs_df
