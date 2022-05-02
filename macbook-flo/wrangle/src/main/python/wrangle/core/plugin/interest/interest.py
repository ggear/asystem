import os
from collections import OrderedDict

import pandas as pd

from .. import library

LABELS = ['Retail', 'Inflation', 'Net']
PERIODS = OrderedDict([
    ('1 Year Mean', 12),
    ('5 Year Mean', 5 * 12),
    ('10 Year Mean', 10 * 12),
    ('20 Year Mean', 20 * 12),
])
COLUMNS = ["{} {}".format(label, period).strip() for label in LABELS for period in ([""] + list(PERIODS.keys()))]

RETAIL_URL = "https://www.rba.gov.au/statistics/tables/xls/f04hist.xls"
INFLATION_URL = "https://www.rba.gov.au/statistics/tables/xls/g01hist.xls"

DRIVE_URL = "https://docs.google.com/spreadsheets/d/10mcrUb5eMn4wz5t0e98-G2uN26v7Km5tyBui2sTkCe8"


class Interest(library.Library):

    def _run(self):
        interest_df = pd.DataFrame()
        interest_delta_df = pd.DataFrame()
        if not library.is_true(library.WRANGLE_DISABLE_DOWNLOAD_FILES):
            new_data = False
            retail_df = pd.DataFrame()
            retail_file = os.path.join(self.input, "retail.xls")
            file_status = self.http_download(RETAIL_URL, retail_file)
            if file_status[0]:
                if library.is_true(library.WRANGLE_REPROCESS_ALL_FILES) or file_status[1]:
                    try:
                        new_data = True
                        retail_raw_df = pd.read_excel(retail_file, skiprows=11, header=None)
                        retail_df['Date'] = pd.to_datetime(retail_raw_df.iloc[:, [0]][0].dt.strftime('%Y-%m-01'))
                        # Column O: Retail deposit and investment rates; Banks' term deposits ($10000); 3 years
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
                if library.is_true(library.WRANGLE_REPROCESS_ALL_FILES) or file_status[1]:
                    try:
                        new_data = True
                        inflation_raw_df = pd.read_excel(inflation_file, skiprows=11, header=None)
                        inflation_df['Date'] = pd.to_datetime(inflation_raw_df.iloc[:, [0]][0].dt.strftime('%Y-%m-01'))
                        # Column E: Year-ended inflation – excluding volatile items
                        inflation_df['Inflation'] = inflation_raw_df.iloc[:, [4]]
                        inflation_df = inflation_df.set_index('Date')
                        self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                    except Exception as exception:
                        self.print_log("Unexpected error processing file [{}]".format(inflation_file), exception)
                        self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
                else:
                    self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED)
            else:
                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
            try:
                if new_data:
                    interest_df = retail_df.merge(inflation_df, left_index=True, right_index=True, how='outer')
                    interest_df = interest_df.dropna(subset=['Retail', 'Inflation'], how='all').ffill().bfill()
                    interest_df['Net'] = interest_df['Retail'] - interest_df['Inflation']
                    interest_df = interest_df.reindex(columns=COLUMNS)
                    interest_df = interest_df[interest_df.index > '1982-03-01']
            except Exception as exception:
                self.print_log("Unexpected error processing interest dataframe", exception)
                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED,
                                 self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED) +
                                 self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED) -
                                 self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED))
        try:
            interest_delta_df, interest_current_df, _ = self.state_cache(interest_df,
                                                                         library.is_true(library.WRANGLE_DISABLE_DOWNLOAD_FILES))
            if len(interest_delta_df):
                data_df = interest_current_df.copy()
                data_df = data_df.set_index(pd.to_datetime(data_df.index)).sort_index()
                data_df.insert(0, "Date", data_df.index.strftime('%Y-%m-%d'))
                data_df = data_df[data_df['Date'] > '2015-01-01'].sort_index(ascending=False)
                data_df[LABELS] = data_df[LABELS].apply(pd.to_numeric)
                for int_rate in LABELS:
                    for int_period in PERIODS:
                        data_df['{} {}'.format(int_rate, int_period)] = data_df[int_rate].rolling(PERIODS[int_period]).mean()
                data_df = data_df.fillna(0)
                self.sheet_write(data_df, DRIVE_URL, {'index': False, 'sheet': 'Interest', 'start': 'A1', 'replace': True})
                self.database_write(data_df[LABELS], global_tags={
                    "type": "mean",
                    "period": "1mo",
                    "unit": "%"
                })
                for int_period in PERIODS:
                    columns = ["{} {}".format(int_rate, int_period).strip() for int_rate in LABELS]
                    columns_rename = {}
                    for column in columns:
                        columns_rename[column] = column.split(" ")[0]
                    self.database_write(data_df[columns].rename(columns=columns_rename), global_tags={
                        "type": "mean",
                        "period": "{}y".format(PERIODS[int_period] / 12),
                        "unit": "%"
                    })
                self.state_write()
        except Exception as exception:
            self.print_log("Unexpected error processing interest data", exception)
            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED,
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED) +
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED) -
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED))
        if not len(interest_delta_df):
            self.print_log("No new data found")
        self.counter_write()

    def __init__(self):
        super(Interest, self).__init__("Interest", "1a20Mmm8j4bz5FneZBPoS9pGDabnnSzUZ")
