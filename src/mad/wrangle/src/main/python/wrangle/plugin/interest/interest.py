import time
from collections import OrderedDict
from datetime import datetime
from os.path import *

import polars as pl
import polars.selectors as cs

from wrangle import plugin
from wrangle.plugin.logger import dataframe_print

LABELS = ['Bank', 'Inflation', 'Net']
PERIODS = OrderedDict([
    ('1 Year Mean', 12),
    ('5 Year Mean', 5 * 12),
    ('10 Year Mean', 10 * 12),
    ('20 Year Mean', 20 * 12),
    ('40 Year Mean', 40 * 12),
])
COLUMNS = [f"{label} {period}".strip() for label in LABELS for period in ([""] + list(PERIODS.keys()))]

RETAIL_URL = "https://www.rba.gov.au/statistics/tables/xls/f04hist.xlsx"
INFLATION_URL = "https://www.rba.gov.au/statistics/tables/xls/g01hist.xlsx"

REPOS_INTEREST = plugin.Repos(
    preview={
        "drive_folder": "1fj4B5JAaDixzcXpjn3R7bGfDQc4DlqHD",
        "sheet_key": "1v3vGZU1x2UGj_-4CIoFIyTXQehFhhlEyyqBI5f-7dDk",
        "database_table": "interest_preview",
    },
    release={
        "drive_folder": "1a20Mmm8j4bz5FneZBPoS9pGDabnnSzUZ",
        "sheet_key": "10mcrUb5eMn4wz5t0e98-G2uN26v7Km5tyBui2sTkCe8",
        "database_table": "interest",
    },
)


class Interest(plugin.Plugin):

    def _run(self):
        interest_df = self.dataframe_new(schema={"Date": pl.Date})
        interest_delta_df = self.dataframe_new()
        if not plugin.config.disable_source_downloads or plugin.config.force_reprocessing:

            # Download Rate Data
            new_data = False
            started_time = time.time()
            started_time_retail = time.time()
            retail_should_read = False
            retail_df = self.dataframe_new(schema={"Date": pl.Date, "Bank": pl.Float64})
            retail_file = join(self.local_cache, "retail.xlsx")
            file_status = self.http_download(RETAIL_URL, retail_file)
            if file_status.status in (plugin.DownloadStatus.CACHED, plugin.DownloadStatus.DOWNLOADED):
                retail_should_read = True
                if plugin.config.force_reprocessing or file_status.status == plugin.DownloadStatus.DOWNLOADED:
                    new_data = True
                    self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_PROCESSED)
                else:
                    self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_SKIPPED)
            elif file_status.status == plugin.DownloadStatus.SKIPPED:
                self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_SKIPPED)
            else:
                self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_ERRORED)

            started_time_inflation = time.time()
            inflation_should_read = False
            inflation_df = self.dataframe_new(schema={"Date": pl.Date, "Inflation": pl.Float64})
            inflation_file = join(self.local_cache, "inflation.xlsx")
            file_status = self.http_download(INFLATION_URL, inflation_file)
            if file_status.status in (plugin.DownloadStatus.CACHED, plugin.DownloadStatus.DOWNLOADED):
                inflation_should_read = True
                if plugin.config.force_reprocessing or file_status.status == plugin.DownloadStatus.DOWNLOADED:
                    new_data = True
                    self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_PROCESSED)
                else:
                    self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_SKIPPED)
            elif file_status.status == plugin.DownloadStatus.SKIPPED:
                self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_SKIPPED)
            else:
                self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_ERRORED)
            interest_downloaded = self.get_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_PROCESSED)
            interest_cached = self.get_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_SKIPPED)
            self.print_log(f"Files downloaded [{interest_downloaded}] and cached [{interest_cached}]", started=started_time)
            if new_data:
                try:

                    # Collect Rate Data
                    if retail_should_read:
                        retail_df = self.excel_read(retail_file, schema={"Series ID": pl.Date}, skip_rows=10, print_rows=12)

                        # NOTE: Select Term Deposit >$10k deposit, 3-year term
                        retail_df = retail_df.select([pl.col("Series ID").alias("Date"), pl.col("FRDIRBTD10K3Y").alias("Bank")])

                        retail_df = retail_df.with_columns((pl.col("Date").dt.strftime('%Y-%m-01').str.to_date()).alias("Date"))
                    if inflation_should_read:
                        inflation_df = self.excel_read(inflation_file, schema={"Series ID": pl.Date}, skip_rows=10, print_rows=12)

                        # NOTE: Select Annual Consumer Price Index
                        inflation_df = inflation_df.select([pl.col("Series ID").alias("Date"), pl.col("GCPIAGYP").alias("Inflation")])

                        inflation_df = inflation_df.with_columns((pl.col("Date").dt.strftime('%Y-%m-01').str.to_date()).alias("Date"))
                except Exception as exception:
                    self.print_log("Unexpected error processing interest source files", exception=exception)
                    self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_ERRORED)
                    new_data = False
                    retail_df = self.dataframe_new(schema={"Date": pl.Date, "Bank": pl.Float64})
                    inflation_df = self.dataframe_new(schema={"Date": pl.Date, "Inflation": pl.Float64})

            retail_df = retail_df if len(retail_df) == 0 else retail_df.fill_nan(pl.lit(None)).drop_nulls()
            dataframe_print(self.name, retail_df, print_label="Retail", print_verb="collected", started=started_time_retail)
            inflation_df = inflation_df if len(inflation_df) == 0 else inflation_df.fill_nan(pl.lit(None)).drop_nulls()
            dataframe_print(self.name, inflation_df, print_label="Inflation", print_verb="collected", started=started_time_inflation)

            # Process Rate Data
            try:
                if new_data:
                    started_time_inner = time.time()
                    interest_df = retail_df.join(inflation_df, on="Date", how="full", coalesce=True).sort("Date").set_sorted("Date")
                    dataframe_print(self.name, interest_df, print_label="Interest", print_verb="post unique", started=started_time_inner)
                    started_time_inner = time.time()
                    interest_df = interest_df.upsample(time_column="Date", every="1mo").fill_nan(pl.lit(None)).sort("Date")
                    interest_df = interest_df.with_columns(pl.all().forward_fill()).drop_nulls()
                    interest_df = interest_df.with_columns((pl.col("Bank") - pl.col("Inflation")).alias("Net"))
                    interest_df = interest_df.with_columns(cs.float().round(2))
                    if "Date_right" in interest_df.columns:
                        interest_df = interest_df.drop("Date_right")
                    dataframe_print(self.name, interest_df, print_label="Interest", print_verb="post up-sample", started=started_time_inner)
            except Exception as exception:
                self.print_log("Unexpected error processing interest dataframe", exception=exception)
                self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_ERRORED,
                                 self.get_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_PROCESSED) +
                                 self.get_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_SKIPPED) -
                                 self.get_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_ERRORED))

        try:
            def _aggregate_function(_data_df):
                _columns = ["Date"]
                for rate in LABELS:
                    _columns.append(rate)
                    for _period in PERIODS:
                        _column = f'{rate} {_period}'
                        _columns.append(_column)
                        _data_df = _data_df.with_columns(
                            (pl.col(rate).rolling_mean(window_size=PERIODS[_period])).alias(_column))
                return _data_df.select(_columns).with_columns(cs.float().round(2))

            # Commit Rate Data: source-complete monthly Bank/Inflation/Net rates → committed state with derived rolling means (delta for egress)
            interest_delta_df, interest_current_df, _ = self.state_cache(interest_df, _aggregate_function)

            # Upload Data
            started_time = time.time()
            if len(interest_delta_df):
                interest_sheet_df = interest_current_df.filter(pl.col("Date") > pl.lit(datetime(2015, 1, 1))).sort("Date", descending=True)
                self.sheet_upload(interest_sheet_df, self.remote_repos.sheet_key, workbook_name="Rates", sheet_name='Interest')
                self.database_upload(interest_current_df.select(["Date"] + LABELS),
                                     metric_type="mean", period="1mo", unit="%",
                                     print_label="Interest_1_Month_Mean")
                for int_period in PERIODS:
                    interest_periodly_df = interest_current_df.select(["Date"] + [f"{int_rate} {int_period}".strip() for int_rate in LABELS])
                    interest_periodly_df.columns = ["Date"] + LABELS
                    self.database_upload(interest_periodly_df,
                                         metric_type="mean", period=f"{PERIODS[int_period] / 12:0.0f}y", unit="%",
                                         print_label=f"Interest_{int_period}".replace(" ", "_"))

            self.print_log("Upload complete", started=started_time)

        except Exception as exception:
            self.print_log("Unexpected error processing interest data", exception=exception)
            self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_ERRORED,
                             self.get_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_PROCESSED) +
                             self.get_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_SKIPPED) -
                             self.get_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_ERRORED))

        if not len(interest_delta_df):
            self.print_log("No new data found")
        self.counter_write()

    def __init__(self):
        super().__init__("Interest", REPOS_INTEREST)
