import datetime
import time
from collections import OrderedDict
from os.path import *

import polars as pl
import polars.selectors as cs

from wrangle import plugin
from wrangle.plugin.logger import dataframe_print

PAIRS = ['AUD/USD', 'AUD/GBP', 'AUD/SGD']

PERIODS = OrderedDict([
    ('1 Day Delta', 1),
    ('1 Week Delta', 7),
    ('1 Month Delta', 30),
    ('1 Year Delta', 365),
])
COLUMNS = [f"{pair} {period}".strip() for pair in PAIRS for period in ([""] + list(PERIODS.keys()))]

RBA_YEARS = [
    "1983-1986",
    "1987-1990",
    "1991-1994",
    "1995-1998",
    "1999-2002",
    "2003-2006",
    "2007-2009",
    "2010-2013",
    "2014-2017",
    "2018-2022",
    "2023-current"
]

RBA_URL = "https://www.rba.gov.au/statistics/tables/xls-hist/{}.xls"


class Currency(plugin.Plugin):
    _repos = plugin.Repos(
        preview={
            "drive_folder": "PLACEHOLDER",
            "sheet_rates": "PLACEHOLDER",
        },
        release={
            "drive_folder": "1_RhzDdkh9PvZ4VsRtsTwfvUMLj6S3QzE",
            "sheet_rates": "10mcrUb5eMn4wz5t0e98-G2uN26v7Km5tyBui2sTkCe8",
        },
    )

    def _run(self):
        rba_df = self.dataframe_new(schema={"Date": pl.Date, **{pair: pl.Float64 for pair in PAIRS}, "Source": pl.Utf8})
        rba_delta_df = self.dataframe_new()
        if not plugin.config.disable_downloads:

            # Download currency data
            new_data = False
            started_time = time.time()
            rba_files_count = 0
            for years in RBA_YEARS:
                years_file = join(self.local_cache, f"RBA_FX_{years}.xls")
                file_status = self.http_download(f"https://www.rba.gov.au/statistics/tables/xls-hist/{years}.xls", years_file, check='current' in years)
                if file_status.status != plugin.DownloadStatus.FAILED:
                    rba_files_count += 1
                    if plugin.config.force_reprocessing or file_status.status == plugin.DownloadStatus.DOWNLOADED:
                        new_data = True
                        try:
                            rba_itr_df = self.excel_read(years_file, schema={"Series ID": pl.Date}, skip_rows=10, na_values=["CLOSED", "Closed", " --"])
                            rba_itr_df = rba_itr_df.select(["Series ID", "FXRUSD", "FXRUKPS", "FXRSD"])
                            rba_itr_df.columns = ['Date'] + PAIRS
                            rba_itr_df = rba_itr_df.with_columns(pl.lit("RBA").alias("Source"))
                            rba_df = pl.concat([rba_df, rba_itr_df])
                            dataframe_print(self.name, rba_df, print_label="RBA_FX", print_verb="concatenated")
                            self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_PROCESSED)
                        except Exception as exception:
                            self.print_log(f"Unexpected error processing file [{years_file}]", exception=exception)
                            self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_ERRORED)
                    else:
                        self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_SKIPPED)
                else:
                    self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_ERRORED)
            if datetime.datetime.now().year > 2027:
                error_message = "RBA_YEARS needs to be incremented for a new current file"
                self.print_log(error_message)
                self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_ERRORED, 1)
                raise RuntimeError(error_message)
            rba_df = rba_df if len(rba_df) == 0 else rba_df.drop_nulls()
            self.print_log(f"Files downloaded or cached [{rba_files_count}] files", started=started_time)
            dataframe_print(self.name, rba_df, print_label="Currency", print_verb="collected")

            # Process the currency data
            try:
                if new_data:
                    started_time_inner = time.time()
                    rba_df = rba_df.unique(subset=['Date'], keep="first")
                    rba_df = rba_df.drop_nulls().sort('Date').set_sorted('Date')
                    dataframe_print(self.name, rba_df, print_label="Currency", print_verb="post unique", started=started_time_inner)
                    started_time_inner = time.time()
                    rba_trading_dates = rba_df.select("Date")
                    rba_df = rba_df.upsample(time_column='Date', every="1d").fill_nan(pl.lit(None)).sort('Date')
                    rba_df = rba_df.with_columns(pl.all().forward_fill()).drop_nulls()
                    rba_df = rba_df.join(rba_trading_dates, on="Date", how="inner")
                    rba_df = rba_df.with_columns(cs.float().round(4))
                    dataframe_print(self.name, rba_df, print_label="Currency", print_verb="post up-sample", started=started_time_inner)
            except Exception as exception:
                self.print_log("Unexpected error processing currency dataframe", exception=exception)
                self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_ERRORED,
                                 self.get_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_PROCESSED) +
                                 self.get_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_SKIPPED) -
                                 self.get_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_ERRORED))

        # State checkpoint boundary
        try:
            def _aggregate_function(_data_df):
                _columns = ['Date']
                _prior_df = _data_df.select(["Date"] + PAIRS).sort("Date")
                for _pair in PAIRS:
                    _columns.append(_pair)
                    for _period, _days in PERIODS.items():
                        _column = f'{_pair} {_period}'
                        _columns.append(_column)
                        _data_df = _data_df.with_columns(
                            (pl.col("Date") - pl.duration(days=_days)).alias("__lookup_date")
                        ).sort("__lookup_date").join_asof(
                            _prior_df.select(["Date", _pair]).rename({_pair: "__prior"}),
                            left_on="__lookup_date", right_on="Date", strategy="backward"
                        ).with_columns(
                            ((pl.col(_pair) - pl.col("__prior")) / pl.col("__prior") * 100).alias(_column)
                        ).drop("__lookup_date", "__prior", "Date_right").sort("Date")
                return _data_df.select(_columns).with_columns(cs.float().round(4)).fill_nan(0).fill_null(0)

            if len(rba_df) == 0:
                rba_df = self.dataframe_new(schema={"Date": pl.Date})
            else:
                if "Source" in rba_df.columns:
                    rba_df = rba_df.drop("Source")
                rba_df = rba_df.upsample(time_column='Date', every="1d").with_columns(pl.all().forward_fill()).drop_nulls()

            # Checkpoint the data
            rba_delta_df, rba_current_df, _ = self.state_cache(rba_df, _aggregate_function)

            # Upload the data
            started_time = time.time()
            if len(rba_delta_df):

                # Sheet upload
                rba_sheet_df = rba_current_df.select(['Date'] + PAIRS).filter(pl.col('Date') > pl.lit(datetime.datetime(2006, 1, 1)))
                self.sheet_upload(rba_sheet_df, self.remote_repos.sheet_rates, workbook_name="Rates", sheet_name='Currency')

                # Database upload
                rba_pairs_df = rba_current_df.select(['Date'] + PAIRS)
                self.database_upload(rba_pairs_df.drop_nulls(), tags={
                    "type": "snapshot",
                    "period": "1d",
                    "unit": "$"
                }, print_label="Currency_1_Day_Snapshot")
                for fx_period in PERIODS:
                    rba_pctchnage_df = rba_current_df.select(['Date'] + [f"{fx_pair} {fx_period}".strip() for fx_pair in PAIRS])
                    rba_pctchnage_df.columns = ['Date'] + PAIRS
                    self.database_upload(rba_pctchnage_df.drop_nulls(), tags={
                        "type": "delta",
                        "period": f"{PERIODS[fx_period]:0.0f}d",
                        "unit": "%"
                    }, print_label=f"Currency_{fx_period}".replace(" ", "_"))

            self.print_log("Upload complete", started=started_time)

        except Exception as exception:
            self.print_log("Unexpected error processing currency data", exception=exception)
            self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_ERRORED,
                             self.get_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_PROCESSED) +
                             self.get_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_SKIPPED) -
                             self.get_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_ERRORED))

        if not len(rba_delta_df):
            self.print_log("No new data found")
        self.counter_write()

    def __init__(self):
        super().__init__("Currency", Currency._repos)
