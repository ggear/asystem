import time
from collections import OrderedDict
from datetime import datetime
from os.path import *

import polars as pl
import polars.selectors as cs

from .. import library

LABELS = ['Bank', 'Inflation', 'Net']
PERIODS = OrderedDict([
    ('1 Year Mean', 12),
    ('5 Year Mean', 5 * 12),
    ('10 Year Mean', 10 * 12),
    ('20 Year Mean', 20 * 12),
    ('30 Year Mean', 30 * 12),
])
COLUMNS = ["{} {}".format(label, period).strip() for label in LABELS for period in ([""] + list(PERIODS.keys()))]

RETAIL_URL = "https://www.rba.gov.au/statistics/tables/xls/f04hist.xls"
INFLATION_URL = "https://www.rba.gov.au/statistics/tables/xls/g01hist.xls"

DRIVE_KEY = "10mcrUb5eMn4wz5t0e98-G2uN26v7Km5tyBui2sTkCe8"


class Interest(library.Library):

    def _run(self):
        interest_df = self.dataframe_new()
        interest_delta_df = self.dataframe_new()
        if not library.test(library.WRANGLE_DISABLE_FILE_DOWNLOAD):
            new_data = False
            started_time = time.time()
            retail_df = self.dataframe_new()
            retail_file = join(self.input, "Retail.xls")
            file_status = self.http_download(RETAIL_URL, retail_file)
            if file_status[0]:
                if library.test(library.WRANGLE_DISABLE_DATA_DELTA) or file_status[1]:
                    try:
                        new_data = True
                        retail_df = self.excel_read(retail_file, schema={"Series ID": pl.Date}, skip_rows=10, print_rows=12)
                        retail_df = retail_df.select([pl.col("Series ID").alias("Date"), pl.col("FRDIRBTD10K3Y").alias("Bank")])
                        retail_df = retail_df.with_columns((pl.col("Date").dt.strftime('%Y-%m-01').str.to_date()).alias("Date"))
                        self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                    except Exception as exception:
                        self.print_log("Unexpected error processing file [{}]".format(retail_file), exception=exception)
                        self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
                else:
                    self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED)
            else:
                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
            retail_df = retail_df.fill_nan(pl.lit(None)).drop_nulls()
            self.dataframe_print(retail_df, print_label="Retail", print_verb="collected", started=started_time)
            started_time = time.time()
            inflation_df = self.dataframe_new()
            inflation_file = join(self.input, "Inflation.xls")
            file_status = self.http_download(INFLATION_URL, inflation_file)
            if file_status[0]:
                if library.test(library.WRANGLE_DISABLE_DATA_DELTA) or file_status[1]:
                    try:
                        new_data = True
                        inflation_df = self.excel_read(inflation_file, schema={"Series ID": pl.Date}, skip_rows=10, print_rows=12)
                        inflation_df = inflation_df.select([pl.col("Series ID").alias("Date"), pl.col("GCPIXVIYP").alias("Inflation")])
                        inflation_df = inflation_df.with_columns((pl.col("Date").dt.strftime('%Y-%m-01').str.to_date()).alias("Date"))
                        self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                    except Exception as exception:
                        self.print_log("Unexpected error processing file [{}]".format(inflation_file), exception=exception)
                        self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
                else:
                    self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED)
            else:
                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
            inflation_df = inflation_df.fill_nan(pl.lit(None)).drop_nulls()
            self.dataframe_print(inflation_df, print_label="Inflation", print_verb="collected", started=started_time)
            try:
                if new_data:
                    started_time = time.time()
                    interest_df = retail_df.join(inflation_df, on="Date", how="outer").sort("Date").set_sorted("Date")
                    self.dataframe_print(interest_df, print_label="Interest", print_verb="post unique", started=started_time)
                    started_time = time.time()
                    interest_df = interest_df.upsample(time_column="Date", every="1mo").fill_nan(pl.lit(None)).sort("Date")
                    interest_df = interest_df.with_columns(pl.all().forward_fill()).drop_nulls()
                    interest_df = interest_df.with_columns(((pl.col("Bank") - pl.col("Inflation"))).alias("Net"))
                    interest_df = interest_df.with_columns(cs.float().round(2))
                    self.dataframe_print(interest_df, print_label="Interest", print_verb="post up-sample", started=started_time)
            except Exception as exception:
                self.print_log("Unexpected error processing interest dataframe", exception=exception)
                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED,
                                 self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED) +
                                 self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED) -
                                 self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED))
        try:
            def _aggregate_function(_data_df):
                _columns = ["Date"]
                for rate in LABELS:
                    _columns.append(rate)
                    for _period in PERIODS:
                        _column = '{} {}'.format(rate, _period)
                        _columns.append(_column)
                        _data_df = _data_df.with_columns(
                            (pl.col(rate).rolling_mean(window_size=PERIODS[_period])).alias(_column))
                return _data_df.select(_columns).with_columns(cs.float().round(2)).fill_nan(0).fill_null(0)

            interest_delta_df, interest_current_df, _ = self.state_cache(interest_df, _aggregate_function)
            if len(interest_delta_df):
                interest_sheet_df = interest_current_df \
                    .filter(pl.col("Date") > pl.lit(datetime(2015, 1, 1))).sort("Date", descending=True)
                self.sheet_upload(interest_sheet_df, DRIVE_KEY, 'Interest')
                started_time = time.time()
                interest_monthly_df = interest_current_df.select(["Date"] + LABELS)
                self.stdout_write(
                    self.dataframe_to_lineprotocol(interest_monthly_df.drop_nulls(), tags={
                        "type": "mean",
                        "period": "1mo",
                        "unit": "%"
                    }, print_label="Interest_1_Month_Mean"))
                for int_period in PERIODS:
                    interest_periodly_df = interest_current_df \
                        .select(["Date"] + ["{} {}".format(int_rate, int_period).strip() for int_rate in LABELS])
                    interest_periodly_df.columns = ["Date"] + LABELS
                    self.stdout_write(
                        self.dataframe_to_lineprotocol(interest_periodly_df.drop_nulls(), tags={
                            "type": "mean",
                            "period": "{:0.0f}y".format(PERIODS[int_period] / 12),
                            "unit": "%"
                        }, print_label="Interest_{}".format(int_period).replace(" ", "_")))
                self.print_log("LineProtocol [Interest] serialised", started=started_time)
        except Exception as exception:
            self.print_log("Unexpected error processing interest data", exception=exception)
            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED,
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED) +
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED) -
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED))
        if not len(interest_delta_df):
            self.print_log("No new data found")
        self.counter_write()

    def __init__(self):
        super(Interest, self).__init__("Interest", "1a20Mmm8j4bz5FneZBPoS9pGDabnnSzUZ")
