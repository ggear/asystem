from __future__ import print_function

import os

import pandas as pd

from .. import library

PERIODS = {'Yearly Test': 12, 'Quinquennialy': 5 * 12, 'Decennialy': 10 * 12, 'Vicennialy': 20 * 12}

RETAIL_URL = "https://www.rba.gov.au/statistics/tables/xls/f04hist.xls"
INFLATION_URL = "https://www.rba.gov.au/statistics/tables/xls/g01hist.xls"

DRIVE_URL = "https://docs.google.com/spreadsheets/d/10mcrUb5eMn4wz5t0e98-G2uN26v7Km5tyBui2sTkCe8"

LINE_PROTOCOL = "interest,source={},type={},period={} {}="


class Interest(library.Library):

    def run(self):
        new_data = False
        retail_df = pd.DataFrame()
        retail_file = os.path.join(self.input, "retail.xls")
        file_status = self.http_download(RETAIL_URL, retail_file)
        if file_status[0]:
            new_data = file_status[1]
            retail_raw_df = pd.read_excel(retail_file, skiprows=11, header=None)
            retail_df['Date'] = pd.to_datetime(retail_raw_df.iloc[:, [0]][0].dt.strftime('%Y-%m-01'))
            retail_df['Retail'] = retail_raw_df.iloc[:, [14]]
            retail_df = retail_df.set_index('Date')

        inflation_df = pd.DataFrame()
        inflation_file = os.path.join(self.input, "inflation.xls")
        file_status = self.http_download(INFLATION_URL, inflation_file)
        if file_status[0]:
            new_data = file_status[1]
            inflation_raw_df = pd.read_excel(inflation_file, skiprows=11, header=None)
            inflation_df['Date'] = pd.to_datetime(inflation_raw_df.iloc[:, [0]][0].dt.strftime('%Y-%m-01'))
            inflation_df['Inflation'] = inflation_raw_df.iloc[:, [3]]
            inflation_df = inflation_df.set_index('Date')

        if new_data:
            interest_df = retail_df.merge(inflation_df, left_index=True, right_index=True, how='outer')
            interest_df = interest_df.dropna(subset=['Retail', 'Inflation'], how='all').fillna(method='ffill').fillna(method='bfill')
            interest_df['Net'] = interest_df['Retail'] - interest_df['Inflation']
            for int_rate in ['Retail', 'Inflation', 'Net']:
                for int_period in PERIODS:
                    interest_df['{} {}'.format(int_rate, int_period)] = interest_df[int_rate].rolling(PERIODS[int_period]).mean()
            interest_df = interest_df.fillna(0)

            self.print_log("Files for [Retail] produced raw data from [{}] to [{}] in [{}] rows"
                           .format(retail_df.index[0].strftime('%d-%m-%Y'), retail_df.index[-1].strftime('%d-%m-%Y'), len(retail_df)))
            self.print_log("Files for [Inflation] produced raw data from [{}] to [{}] in [{}] rows"
                           .format(inflation_df.index[0].strftime('%d-%m-%Y'), inflation_df.index[-1].strftime('%d-%m-%Y'),
                                   len(inflation_df)))
            self.print_log("Files for [Retail + Inflation] produced processed data from [{}] to [{}] in [{}] rows"
                           .format(interest_df.index[0].strftime('%d-%m-%Y'), interest_df.index[-1].strftime('%d-%m-%Y'), len(interest_df)))
            interest_delta_df = self.drive_sync_delta(interest_df, "interest")
            if len(interest_delta_df):
                self.write_sheet(interest_df.iloc[::-1], DRIVE_URL,
                                 {'index': True, 'sheet': 'Interest', 'start': 'A1', 'replace': True})
                for int_rate in ['Retail', 'Inflation', 'Net']:
                    self.write_database("\n".join(LINE_PROTOCOL.format("RBA", "snapshot", "monthly", int_rate.lower()) +
                                                  interest_delta_df[int_rate].map(str) +
                                                  " " + (pd.to_datetime(interest_delta_df.index).astype(int) +
                                                         6 * 60 * 60 * 1000000000).map(str)))
                    for int_period in PERIODS:
                        self.write_database("\n".join(LINE_PROTOCOL.format("RBA", "mean", int_period.lower(), int_rate.lower()) +
                                                      interest_delta_df["{} {}".format(int_rate, int_period)].map(str) +
                                                      " " + (pd.to_datetime(interest_delta_df.index).astype(int) +
                                                             6 * 60 * 60 * 1000000000).map(str)))
            else:
                new_data = False
        if not new_data:
            self.print_log("No new data found")

    def __init__(self):
        super(Interest, self).__init__("Interest", "1a20Mmm8j4bz5FneZBPoS9pGDabnnSzUZ", "1RSp8wFfHQX9qHebFArQRuWZs34Lq46r8")
