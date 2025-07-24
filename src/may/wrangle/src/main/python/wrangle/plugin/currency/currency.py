import datetime
import time
from collections import OrderedDict
from datetime import datetime
from os.path import *

import polars as pl
import polars.selectors as cs

from .. import library

PAIRS = ['AUD/USD', 'AUD/GBP', 'AUD/SGD']

PERIODS = OrderedDict([
    ('1 Day Delta', 1),
    ('1 Week Delta', 7),
    ('1 Month Delta', 30),
    ('1 Year Delta', 365),
])
COLUMNS = ["{} {}".format(pair, period).strip() for pair in PAIRS for period in ([""] + list(PERIODS.keys()))]

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
    "2014-2017",
    "2018-2022",
    "2023-current"
]

RBA_URL = "https://www.rba.gov.au/statistics/tables/xls-hist/{}.xls"

DRIVE_KEY = "10mcrUb5eMn4wz5t0e98-G2uN26v7Km5tyBui2sTkCe8"


class Currency(library.Library):

    def _run(self):
        rba_df = self.dataframe_new()
        rba_delta_df = self.dataframe_new()
        if not library.test(library.WRANGLE_DISABLE_FILE_DOWNLOAD):
            new_data = False
            started_time = time.time()
            for years in RBA_YEARS:
                years_file = join(self.input, "RBA_FX_{}.xls".format(years))
                file_status = self.http_download(RBA_URL.format(years), years_file, check='current' in years)
                if file_status[0]:
                    if library.test(library.WRANGLE_DISABLE_DATA_DELTA) or file_status[1]:
                        new_data = True
                        try:
                            rba_itr_df = self.excel_read(years_file, schema={"Series ID": pl.Date},
                                                         skip_rows=10, na_values=["CLOSED", "Closed", " --"])
                            rba_itr_df = rba_itr_df.select(["Series ID", "FXRUSD", "FXRUKPS", "FXRSD"])
                            rba_itr_df.columns = ['Date'] + PAIRS
                            rba_itr_df = rba_itr_df.with_columns(pl.lit("RBA").alias("Source"))
                            rba_df = pl.concat([rba_df, rba_itr_df])
                            self.dataframe_print(rba_df, print_label="RBA_FX", print_verb="concatenated")
                            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                        except Exception as exception:
                            self.print_log("Unexpected error processing file [{}]".format(years_file), exception=exception)
                            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
                    else:
                        self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED)
                else:
                    self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
            if datetime.now().year > 2027:
                self.print_log("Error processing RBA data, need to increment RBA_YEARS for new current file")
                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED, 1)
                return
            rba_df = rba_df if len(rba_df) == 0 else rba_df.drop_nulls()
            self.dataframe_print(rba_df, print_label="Currency", print_verb="collected", started=started_time)
            try:
                if new_data:
                    started_time = time.time()
                    rba_df = rba_df.unique(subset=['Date'], keep="first").drop("Source").drop_nulls().sort('Date').set_sorted('Date')
                    self.dataframe_print(rba_df, print_label="Currency", print_verb="post unique", started=started_time)
                    started_time = time.time()
                    rba_df = rba_df.upsample(time_column='Date', every="1d").fill_nan(pl.lit(None)).sort('Date')
                    rba_df = rba_df.with_columns(pl.all().forward_fill()).drop_nulls()
                    rba_df = rba_df.with_columns(cs.float().round(4))
                    self.dataframe_print(rba_df, print_label="Currency", print_verb="post up-sample", started=started_time)
            except Exception as exception:
                self.print_log("Unexpected error processing currency dataframe", exception=exception)
                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED,
                                 self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED) +
                                 self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED) -
                                 self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED))
        try:
            def _aggregate_function(_data_df):
                _columns = ['Date']
                for _pair in PAIRS:
                    _columns.append(_pair)
                    for _period in PERIODS:
                        _column = '{} {}'.format(_pair, _period)
                        _columns.append(_column)
                        _data_df = _data_df.with_columns((pl.col(_pair).pct_change() * 100).alias(_column))
                return _data_df.select(_columns).with_columns(cs.float().round(4)).fill_nan(0).fill_null(0)

            rba_delta_df, rba_current_df, _ = self.state_cache(rba_df, _aggregate_function)
            if len(rba_delta_df):
                rba_sheet_df = rba_current_df.select(['Date'] + PAIRS).filter(pl.col('Date') > pl.lit(datetime(2006, 1, 1)))
                self.sheet_upload(rba_sheet_df, DRIVE_KEY, 'Currency')
                started_time = time.time()
                rba_pairs_df = rba_current_df.select(['Date'] + PAIRS)
                self.stdout_write(
                    self.dataframe_to_lineprotocol(rba_pairs_df.drop_nulls(), tags={
                        "type": "snapshot",
                        "period": "1d",
                        "unit": "$"
                    }, print_label="Currency_1_Day_Snapshot"))
                for fx_period in PERIODS:
                    rba_pctchnage_df = rba_current_df \
                        .select(['Date'] + ["{} {}".format(fx_pair, fx_period).strip() for fx_pair in PAIRS])
                    rba_pctchnage_df.columns = ['Date'] + PAIRS
                    self.stdout_write(
                        self.dataframe_to_lineprotocol(rba_pctchnage_df.drop_nulls(), tags={
                            "type": "delta",
                            "period": "{:0.0f}d".format(PERIODS[fx_period]),
                            "unit": "%"
                        }, print_label="Currency_{}".format(fx_period).replace(" ", "_")))
                self.print_log("LineProtocol [Currency] serialised", started=started_time)
        except Exception as exception:
            self.print_log("Unexpected error processing currency data", exception=exception)
            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED,
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED) +
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED) -
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED))
        if not len(rba_delta_df):
            self.print_log("No new data found")
        self.counter_write()

    def __init__(self):
        super(Currency, self).__init__("Currency", "1_RhzDdkh9PvZ4VsRtsTwfvUMLj6S3QzE")
