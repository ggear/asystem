from __future__ import print_function

import calendar
import datetime
import os
import re

import pandas as pd

from .. import script

DIR_DRIVE = ""

PAIRS = ['AUD/GBP', 'AUD/USD', 'AUD/SGD']
PERIODS = {'Daily': 1, 'Weekly': 7, 'Monthly': 30, 'Yearly': 365}

ATO_START_MONTH = 5
ATO_START_YEAR = 2016
ATO_FINISH_YEAR = 2020
ATO_XLS_HEADER_ROWS = [5, 3, 2, 1, 4, 0, 6]
ATO_URL_SUFFIX = [
    "{}_{}_daily_rates.xlsx",
    "{}_{}_daily_input.xlsx",
    "{}{}dailyinput.xlsx",
    "{}-{}-daily-input.xlsx",
    "{1}_{0}_daily_input.xlsx",
    "{1}_{0}_Daily_%20input.xlsx",
    "{}%20{}%20daily%20input.xlsx",
    "{}%20{}%20daily%20input.xls.xlsx"
]
ATO_URL_PREFIX = "https://www.ato.gov.au/uploadedFiles/Content/TPALS/downloads/"

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
    "2018-current"
]
RBA_URL = "https://www.rba.gov.au/statistics/tables/xls-hist/{}.xls"

DRIVE_RATES_URL = "https://docs.google.com/spreadsheets/d/10mcrUb5eMn4wz5t0e98-G2uN26v7Km5tyBui2sTkCe8"
LINE_PROTOCOL = "currency,source={},type={},period={} {}="


# TODO:
#  - Update HTTP to check update timestamps
#  - Only push if there are new files
#  - Convert print statements
#  - Update influx/gsheet uploads to use script functions
#  - Push files to Drive

class Currency(script.Script):

    def run(self):
        rba_df = pd.DataFrame()
        ato_df = pd.DataFrame()
        merged_df = pd.DataFrame()
        for year in range(ATO_START_YEAR, ATO_FINISH_YEAR):
            for month in range(1 if year != ATO_START_YEAR else ATO_START_MONTH,
                               13 if year < datetime.datetime.now().year else datetime.datetime.now().month):
                month_string = datetime.date(2000, month, 1).strftime('%B')
                year_month_file = os.path.join(self.input, "ato_fx_{}-{}.xls".format(year, str(month).zfill(2)))
                for url_suffix in ATO_URL_SUFFIX:
                    if self.http_download((ATO_URL_PREFIX + url_suffix).format(month_string, year), year_month_file):
                        break
                for header_rows in ATO_XLS_HEADER_ROWS:
                    ato_df = pd.read_excel(year_month_file, skiprows=header_rows)
                    if ato_df.columns[0] == 'Country':
                        ato_df = ato_df[ato_df['Country'].isin(['USA', 'UK', 'SINGAPORE'])]
                        for column in ato_df.columns:
                            if isinstance(column, basestring) and column != 'Country':
                                if column[0].isdigit():
                                    match = re.compile("(.*)-(.*)").match(column)
                                    ato_df.rename(columns={column: "{}-{}-{}".format(
                                        year,
                                        str(list(calendar.month_abbr).index(match.group(2))).zfill(2),
                                        match.group(1).zfill(2)
                                    )}, inplace=True)
                                else:
                                    ato_df.drop(column, axis=1, inplace=True)
                            elif isinstance(column, datetime.datetime):
                                ato_df.rename(columns={column: column.strftime("{}-%m-%d".format(year))}, inplace=True)
                        ato_df = ato_df.melt('Country', var_name='Date', value_name='Rate'). \
                            pivot_table('Rate', ['Date'], 'Country', aggfunc='first'). \
                            fillna(method='ffill').fillna(method='bfill').reset_index()
                        ato_df.rename(columns={'USA': 'AUD/USD', 'UK': 'AUD/GBP', 'SINGAPORE': 'AUD/SGD'}, inplace=True)
                        ato_df.index.name = None
                        ato_df.columns.name = None
                        ato_df['Source'] = 'ATO'
                        ato_df = ato_df[['Source', 'Date'] + PAIRS]
                        merged_df = merged_df.append(ato_df, ignore_index=True, verify_integrity=True)
                        print("DEBUG [Currency]: {}-{} parsed [{}] with header rows [{}] and data points [{}]".
                              format(year, str(month).zfill(2), 'TRUE', header_rows, len(ato_df)))
                        break
                if ato_df is not None:
                    print("DEBUG [Currency]: {}-{} processed [{}]".format(year, str(month).zfill(2), 'TRUE'))
                else:
                    print("DEBUG [Currency]: {}-{} processed [{}]".format(year, str(month).zfill(2), 'FALSE'))

        for years in RBA_YEARS:
            years_months = (years.replace("-", "-01 to ") + ("2021-01" if years.endswith("current") else "-12")).replace("current", "")
            years_file = os.path.join(self.input, "rba_fx_{}.xls".format(years))
            self.http_download(RBA_URL.format(years), years_file, 'current' in years)
            rba_itr_df = pd.read_excel(years_file, skiprows=10)
            if rba_itr_df.columns[0] == 'Series ID':
                rba_itr_df = rba_itr_df.filter(['Series ID', 'FXRUSD', 'FXRUKPS', 'FXRSD']). \
                    rename(columns={'Series ID': 'Date', 'FXRUSD': 'AUD/USD', 'FXRUKPS': 'AUD/GBP', 'FXRSD': 'AUD/SGD'})
                rba_itr_df['Date'] = rba_itr_df['Date'].dt.strftime("%Y-%m-%d").astype(str)
                rba_itr_df['Source'] = 'RBA'
                rba_itr_df = rba_itr_df[['Source', 'Date'] + PAIRS]
                rba_df = rba_df.append(rba_itr_df, ignore_index=True, verify_integrity=True)
                print("DEBUG [Currency]: {} parsed [{}] with and data points [{}]".format(years_months, 'TRUE', len(rba_itr_df)))

        def extrapolate(data_df):
            data_df = data_df.drop_duplicates(subset='Date', keep="first").copy()
            data_df['Date'] = pd.to_datetime(data_df['Date'])
            data_df = data_df.set_index('Date').sort_index()
            date_start = "{}-{}".format(data_df.index[0].year, str(data_df.index[0].month).zfill(2))
            date_finish = "{}-{}".format(data_df.index[-1].year, str(data_df.index[-1].month).zfill(2))
            print("DEBUG [Currency]: {} to {} collated with rows [{}]".format(date_start, date_finish, len(data_df)))
            for fx_pair in PAIRS:
                data_df = data_df[~data_df[fx_pair].isin(['Closed', 'CLOSED'])]
            data_df = data_df.reindex(
                pd.date_range(start=data_df.index[0], end=data_df.index[-1])).fillna(method='ffill').fillna(method='bfill')
            data_df['Date'] = data_df.index.strftime("%Y-%m-%d")
            data_df = data_df[['Source', 'Date'] + PAIRS]
            for fx_pair in PAIRS:
                for fx_period in PERIODS:
                    data_df['{} {}'.format(fx_pair, fx_period)] = (data_df[fx_pair].pct_change(PERIODS[fx_period])) * 100
            data_df = data_df.fillna(0)
            print("DEBUG [Currency]: {} to {} extrapolated with rows [{}]".format(date_start, date_finish, len(data_df)))
            return date_start, date_finish, data_df

        if datetime.datetime.now().year > 2021:
            print("DEBUG [Currency]: {}-{} processed [{}], update [RBA_YEARS]".format(2022, '01', 'FALSE'))
        merged_df = rba_df.append(ato_df, ignore_index=True, verify_integrity=True)
        merged_tupple = extrapolate(merged_df)

        # TODO: Uncomment
        # Spread(DRIVE_RATES_URL).df_to_sheet(merged_tupple[2], index=False, sheet='FX', start='A1', replace=True)

        print(
            "DEBUG [Currency]: {} to {} uploaded to Drive with rows [{}]".format(merged_tupple[0], merged_tupple[1], len(merged_tupple[2])))

        rba_tupple = extrapolate(rba_df)
        for fx_pair in PAIRS:
            print("\n".join(LINE_PROTOCOL.format("RBA", "snapshot", "daily", fx_pair) +
                            rba_tupple[2][fx_pair].map(str) +
                            " " + (pd.to_datetime(rba_tupple[2]['Date']).astype(int) + 6 * 60 * 60 * 1000000000).map(str)))
            for fx_period in PERIODS:
                print("\n".join(LINE_PROTOCOL.format("RBA", "delta", fx_period.lower(), fx_pair) +
                                rba_tupple[2]["{} {}".format(fx_pair, fx_period)].map(str) +
                                " " + (pd.to_datetime(rba_tupple[2]['Date']).astype(int) + 6 * 60 * 60 * 1000000000).map(str)))
        print("DEBUG [Currency]: {} to {} output with rows [{}]".format(rba_tupple[0], rba_tupple[1], len(rba_tupple[2])))

    def __init__(self):
        super(Currency, self).__init__("Currency")
