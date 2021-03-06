# -*- coding: utf-8 -*-

from __future__ import print_function

import calendar
import datetime
import os
import re
from collections import OrderedDict

import pandas as pd

from .. import library

PAIRS = ['AUD/GBP', 'AUD/USD', 'AUD/SGD']
PERIODS = OrderedDict([
    ('1 Day Delta', 1),
    ('1 Week Delta', 7),
    ('1 Month Delta', 30),
    ('1 Year Delta', 365),
])
COLUMNS = ["{} {}".format(pair, period).strip() for pair in PAIRS for period in ([""] + PERIODS.keys())]

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

DRIVE_URL = "https://docs.google.com/spreadsheets/d/10mcrUb5eMn4wz5t0e98-G2uN26v7Km5tyBui2sTkCe8"

LINE_PROTOCOL = "currency,type={},period={},unit={} {}="


class Currency(library.Library):

    def _run(self):
        new_data = False
        rba_df = pd.DataFrame()
        ato_df = pd.DataFrame()
        merged_df = pd.DataFrame()
        for year in range(ATO_START_YEAR, ATO_FINISH_YEAR):
            for month in range(1 if year != ATO_START_YEAR else ATO_START_MONTH,
                               13 if year < datetime.datetime.now().year else datetime.datetime.now().month):
                month_string = datetime.date(2000, month, 1).strftime('%B')
                year_month_file = os.path.join(self.input, "ato_fx_{}-{}.xls".format(year, str(month).zfill(2)))
                year_month_file_downloaded = False
                for url_suffix in ATO_URL_SUFFIX:
                    file_status = self.http_download((ATO_URL_PREFIX + url_suffix)
                                                     .format(month_string, year), year_month_file, check=False, ignore=True)
                    if file_status[0]:
                        year_month_file_downloaded = True
                        if os.getenv('WRANGLE_REPROCESS_ALL_FILES') == "true" or file_status[1]:
                            new_data = True
                            for header_rows in ATO_XLS_HEADER_ROWS:
                                try:
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
                                        merged_df = merged_df.append(ato_df, ignore_index=True, verify_integrity=True, sort=True)
                                        self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                                        break
                                except Exception as exception:
                                    self.print_log("Unexpected error processing file [{}]".format(year_month_file), exception)
                        else:
                            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED)
                        break
                if not year_month_file_downloaded:
                    self.print_log("Error downloading file [{}]".format(os.path.basename(year_month_file)))
                    self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
        for years in RBA_YEARS:
            years_file = os.path.join(self.input, "rba_fx_{}.xls".format(years))
            file_status = self.http_download(RBA_URL.format(years), years_file, check='current' in years)
            if file_status[0]:
                if os.getenv('WRANGLE_REPROCESS_ALL_FILES') == "true" or file_status[1]:
                    new_data = True
                    try:
                        rba_itr_df = pd.read_excel(years_file, skiprows=10)
                        if rba_itr_df.columns[0] == 'Series ID':
                            rba_itr_df = rba_itr_df.filter(['Series ID', 'FXRUSD', 'FXRUKPS', 'FXRSD']). \
                                rename(columns={'Series ID': 'Date', 'FXRUSD': 'AUD/USD', 'FXRUKPS': 'AUD/GBP', 'FXRSD': 'AUD/SGD'})
                            rba_itr_df['Date'] = rba_itr_df['Date'].dt.strftime("%Y-%m-%d").astype(str)
                            rba_itr_df['Source'] = 'RBA'
                            rba_itr_df = rba_itr_df[['Source', 'Date'] + PAIRS]
                            rba_df = rba_df.append(rba_itr_df, ignore_index=True, verify_integrity=True, sort=True)
                            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                    except Exception as exception:
                        self.print_log("Unexpected error processing file [{}]".format(year_month_file), exception)
                        self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
                else:
                    self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED)
            else:
                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)

        def extrapolate(data_df):
            data_df = data_df.drop_duplicates(subset='Date', keep="first").copy()
            data_df['Date'] = pd.to_datetime(data_df['Date'])
            data_df = data_df.set_index('Date').sort_index()
            for fx_pair in PAIRS:
                data_df = data_df[~data_df[fx_pair].isin(['Closed', 'CLOSED'])]
            data_df = data_df.reindex(pd.date_range(start=data_df.index[0], end=data_df.index[-1])) \
                .fillna(method='ffill').fillna(method='bfill')
            data_df = data_df[['Source'] + PAIRS]
            data_df.index.name = 'Date'
            for fx_pair in PAIRS:
                for fx_period in PERIODS:
                    data_df['{} {}'.format(fx_pair, fx_period)] = (data_df[fx_pair].pct_change(PERIODS[fx_period])) * 100
            data_df = data_df.fillna(0)
            return data_df

        if datetime.datetime.now().year > 2021:
            self.print_log("Error processing RBA data, need to increment RBA_YEARS for new current file")
            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED, 1)
            return
        if new_data:
            try:

                # TODO: Evaluate whether ATO FX rates should be included or not
                # ato_rba_df = extrapolate(rba_df.append(ato_df, ignore_index=True, verify_integrity=True, sort=True))

                rba_df = extrapolate(rba_df)
                del rba_df['Source']
                rba_df = rba_df.reindex(columns=COLUMNS)
                rba_delta_df, rba_current_df, _ = self.state_cache(rba_df, "Currency")
                if len(rba_delta_df):
                    rba_current_df.index = rba_current_df.index.strftime('%Y-%m-%d')
                    self.sheet_write(rba_current_df, DRIVE_URL, {'index': True, 'sheet': 'Currency', 'start': 'A1', 'replace': True})
                    for fx_pair in PAIRS:
                        self.database_write("\n".join(LINE_PROTOCOL.format("snapshot", "1d",
                                                                           "$/£" if "GBP" in fx_pair else "$/$", fx_pair) +
                                                      rba_delta_df[fx_pair].map(str) +
                                                      " " + (pd.to_datetime(rba_delta_df.index).astype(int) +
                                                             6 * 60 * 60 * 1000000000).map(str)))
                        for fx_period in PERIODS:
                            self.database_write("\n".join(LINE_PROTOCOL.format("delta", "{}d".format(PERIODS[fx_period]),
                                                                               "%", fx_pair) +
                                                          rba_delta_df["{} {}".format(fx_pair, fx_period)].map(str) +
                                                          " " + (pd.to_datetime(rba_delta_df.index).astype(int) +
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
        self.counter_write()

    def __init__(self):
        super(Currency, self).__init__("Currency", "1_RhzDdkh9PvZ4VsRtsTwfvUMLj6S3QzE")
