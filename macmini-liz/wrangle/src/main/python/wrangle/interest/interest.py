from __future__ import print_function

import os

import pandas as pd

from .. import script

PERIODS = {'Yearly': 12, 'Five-Yearly': 5 * 12, 'Decennially': 10 * 12}

RETAIL_URL = "https://www.rba.gov.au/statistics/tables/xls/f04hist.xls"
INFLATION_URL = "https://www.rba.gov.au/statistics/tables/xls/g01hist.xls"
LINE_PROTOCOL = "interest,source={},type={},period={} {}="


# TODO:
#  - Update HTTP to check update timestamps
#  - Only push if there are new files
#  - Convert print statements
#  - Update influx/gsheet uploads to use script functions
#  - Push files to Drive

class Interest(script.Script):

    def run(self):
        interest_df = pd.DataFrame()
        retail_file = os.path.join(self.input, "retail.xls")

        if self.http_download(RETAIL_URL, retail_file, True):
            retail_raw_df = pd.read_excel(retail_file, skiprows=11, header=None)
            interest_df['Date'] = pd.to_datetime(retail_raw_df.iloc[:, [0]][0].dt.strftime('%Y-%m-01'))
            interest_df['Retail'] = retail_raw_df.iloc[:, [14]]
            interest_df = interest_df.set_index('Date')
            print("DEBUG [Retail]: {} to {} extrapolated with rows [{}]".format(
                interest_df.first_valid_index().strftime('%Y-%m'), interest_df.last_valid_index().strftime('%Y-%m'), len(interest_df)))

        inflation_file = os.path.join(self.input, "inflation.xls")
        if self.http_download(INFLATION_URL, inflation_file, True):
            inflation_df = pd.DataFrame()
            inflation_raw_df = pd.read_excel(inflation_file, skiprows=11, header=None)
            inflation_df['Date'] = pd.to_datetime(inflation_raw_df.iloc[:, [0]][0].dt.strftime('%Y-%m-01'))
            inflation_df['Inflation'] = inflation_raw_df.iloc[:, [3]]
            inflation_df = inflation_df.set_index('Date')
            print("DEBUG [Inflation]: {} to {} extrapolated with rows [{}]".format(
                inflation_df.first_valid_index().strftime('%Y-%m'), inflation_df.last_valid_index().strftime('%Y-%m'), len(inflation_df)))
            interest_df = interest_df.merge(inflation_df, left_index=True, right_index=True, how='outer')

        interest_df = interest_df.dropna(subset=['Retail', 'Inflation'], how='all').fillna(method='ffill').fillna(method='bfill')
        interest_df['Net'] = interest_df['Retail'] - interest_df['Inflation']
        for int_rate in ['Retail', 'Inflation', 'Net']:
            for int_period in PERIODS:
                interest_df['{} {}'.format(int_rate, int_period)] = interest_df[int_rate].rolling(PERIODS[int_period]).mean()
        interest_df = interest_df.fillna(0)
        print("DEBUG [Interest]: {} to {} extrapolated with rows [{}]".format(
            interest_df.first_valid_index().strftime('%Y-%m'), interest_df.last_valid_index().strftime('%Y-%m'), len(interest_df)))

        for int_rate in ['Retail', 'Inflation', 'Net']:
            print("\n".join(LINE_PROTOCOL.format("RBA", "snapshot", "monthly", int_rate.lower()) +
                            interest_df[int_rate].map(str) +
                            " " + (pd.to_datetime(interest_df.index).astype(int) + 6 * 60 * 60 * 1000000000).map(str)))
            for int_period in PERIODS:
                print("\n".join(LINE_PROTOCOL.format("RBA", "mean", int_period.lower(), int_rate.lower()) +
                                interest_df["{} {}".format(int_rate, int_period)].map(str) +
                                " " + (pd.to_datetime(interest_df.index).astype(int) + 6 * 60 * 60 * 1000000000).map(str)))
        print("DEBUG [Interest]: {} to {} output with rows [{}]".format(
            interest_df.first_valid_index().strftime('%Y-%m'), interest_df.last_valid_index().strftime('%Y-%m'), len(interest_df)))

    def __init__(self):
        super(Interest, self).__init__("Interest")
