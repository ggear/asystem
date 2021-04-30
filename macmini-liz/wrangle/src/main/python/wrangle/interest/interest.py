from __future__ import print_function

import os
from collections import OrderedDict

import pandas as pd

from .. import library

LABELS = ['Retail', 'Inflation', 'Net']
PERIODS = OrderedDict([
    ('1 YR MA', 12),
    ('5 YR MA', 5 * 12),
    ('10 YR MA', 10 * 12),
    ('20 YR MA', 20 * 12),
])
COLUMNS = ["{} {}".format(label, period).strip() for label in LABELS for period in ([""] + PERIODS.keys())]

RETAIL_URL = "https://www.rba.gov.au/statistics/tables/xls/f04hist.xls"
INFLATION_URL = "https://www.rba.gov.au/statistics/tables/xls/g01hist.xls"

DRIVE_URL = "https://docs.google.com/spreadsheets/d/10mcrUb5eMn4wz5t0e98-G2uN26v7Km5tyBui2sTkCe8"

LINE_PROTOCOL = "interest,type={},period={} {}="


class Interest(library.Library):

    def _run(self):
        new_data = False
        retail_df = pd.DataFrame()
        retail_file = os.path.join(self.input, "retail.xls")
        file_status = self.http_download(RETAIL_URL, retail_file)
        if file_status[0]:
            if file_status[1]:
                try:
                    new_data = True
                    retail_raw_df = pd.read_excel(retail_file, skiprows=11, header=None)
                    retail_df['Date'] = pd.to_datetime(retail_raw_df.iloc[:, [0]][0].dt.strftime('%Y-%m-01'))
                    retail_df['Retail'] = retail_raw_df.iloc[:, [14]]
                    retail_df = retail_df.set_index('Date')
                    self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                except Exception as exception:
                    self.print_log("Unexpected error processing file [{}]".format(retail_file), exception)
                    self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
            else:
                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED)
        else:
            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
        inflation_df = pd.DataFrame()
        inflation_file = os.path.join(self.input, "inflation.xls")
        file_status = self.http_download(INFLATION_URL, inflation_file)
        if file_status[0]:
            if file_status[1]:
                try:
                    new_data = True
                    inflation_raw_df = pd.read_excel(inflation_file, skiprows=11, header=None)
                    inflation_df['Date'] = pd.to_datetime(inflation_raw_df.iloc[:, [0]][0].dt.strftime('%Y-%m-01'))
                    inflation_df['Inflation'] = inflation_raw_df.iloc[:, [3]]
                    inflation_df = inflation_df.set_index('Date')
                    self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                except Exception as exception:
                    self.print_log("Unexpected error processing file [{}]".format(inflation_file), exception)
                    self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
            else:
                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED)
        else:
            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
        if new_data:
            try:
                interest_df = retail_df.merge(inflation_df, left_index=True, right_index=True, how='outer')
                interest_df = interest_df.dropna(subset=['Retail', 'Inflation'], how='all').fillna(method='ffill').fillna(method='bfill')
                interest_df['Net'] = interest_df['Retail'] - interest_df['Inflation']
                for int_rate in LABELS:
                    for int_period in PERIODS:
                        interest_df['{} {}'.format(int_rate, int_period)] = interest_df[int_rate].rolling(PERIODS[int_period]).mean()
                interest_df = interest_df.fillna(0)
                interest_df = interest_df.reindex(columns=COLUMNS)
                interest_df = interest_df[interest_df.index > '1982-03-01']
                interest_delta_df, interest_current_df, _ = self.state_cache(interest_df, "Interest")
                if len(interest_delta_df):
                    self.sheet_write(interest_current_df.iloc[::-1].sort_index(ascending=False), DRIVE_URL,
                                     {'index': True, 'sheet': 'Interest', 'start': 'A1', 'replace': True})
                    for int_rate in LABELS:
                        self.database_write("\n".join(LINE_PROTOCOL.format("snapshot", "monthly", int_rate.lower()) +
                                                      interest_delta_df[int_rate].map(str) +
                                                      " " + (pd.to_datetime(interest_delta_df.index).astype(int) +
                                                             6 * 60 * 60 * 1000000000).map(str)))
                        for int_period in PERIODS:
                            self.database_write("\n".join(LINE_PROTOCOL.format("mean", int_period.lower(), int_rate.lower()) +
                                                          interest_delta_df["{} {}".format(int_rate, int_period)].map(str) +
                                                          " " + (pd.to_datetime(interest_delta_df.index).astype(int) +
                                                                 6 * 60 * 60 * 1000000000).map(str)))
                    self.state_write()
                else:
                    new_data = False
            except Exception as exception:
                self.print_log("Unexpected error processing currency data", exception)
                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED,
                                 self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED) +
                                 self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED) -
                                 self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED))
        if not new_data:
            self.print_log("No new data found")

    def __init__(self, profile_path=".profile"):
        super(Interest, self).__init__("Interest", "1a20Mmm8j4bz5FneZBPoS9pGDabnnSzUZ", profile_path)
