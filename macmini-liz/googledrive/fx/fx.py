#!/usr/bin/env python

import calendar
import os.path
import re
import ssl
import urllib2

import datetime
import pandas as pd
from gspread_pandas import Spread

DATA_DIR_XLS = 'xls'
DATA_DIR_CSV = 'csv'

ATO_START_MONTH = 5
ATO_START_YEAR = 2016
ATO_FINISH_YEAR = 2020
ATO_XLS_HEADER_ROWS = [5, 3, 2, 1, 4, 0, 6]
ATO_URL_PREFIX = "https://www.ato.gov.au/uploadedFiles/Content/TPALS/downloads/"
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

RBA_YEARS = [
    "1983-1986", "1987-1990", "1991-1994", "1995-1998", "1999-2002", "2003-2006", "2007-2009", "2010-2013", "2014-2017", "2018-current"]
RBA_URL = "https://www.rba.gov.au/statistics/tables/xls-hist/{}.xls"

HTTP_HEADER = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
               'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
               'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
               'Accept-Encoding': 'none',
               'Accept-Language': 'en-US,en;q=0.8',
               'Connection': 'keep-alive'}

DRIVE_SHEET = "https://docs.google.com/spreadsheets/d/10mcrUb5eMn4wz5t0e98-G2uN26v7Km5tyBui2sTkCe8"

if not os.path.exists(DATA_DIR_XLS):
    os.makedirs(DATA_DIR_XLS)
if not os.path.exists(DATA_DIR_CSV):
    os.makedirs(DATA_DIR_CSV)

all_df = pd.DataFrame()

for year in range(ATO_START_YEAR, ATO_FINISH_YEAR):
    for month in range(1 if year != ATO_START_YEAR else ATO_START_MONTH,
                       13 if year < datetime.datetime.now().year else datetime.datetime.now().month):
        month_string = datetime.date(2000, month, 1).strftime('%B')
        year_month_file = os.path.join(DATA_DIR_XLS, "ato_fx_{}-{}.xls".format(year, str(month).zfill(2)))
        available = False
        if os.path.isfile(year_month_file):
            print("{}-{} cached [{}]".format(year, str(month).zfill(2), 'TRUE'))
            available = True
        else:
            print("{}-{} cached [{}]".format(year, str(month).zfill(2), 'FALSE'))
            for suffix in ATO_URL_SUFFIX:
                url = (ATO_URL_PREFIX + suffix).format(month_string, year)
                try:
                    month_xls = urllib2.urlopen(urllib2.Request(url, headers=HTTP_HEADER),
                                                context=ssl._create_unverified_context())
                    with open(year_month_file, 'wb') as output:
                        output.write(month_xls.read())
                    print("{}-{} downloaded [{}] from [{}]".format(year, str(month).zfill(2), 'TRUE', url))
                    available = True
                    break
                except:
                    print("{}-{} downloaded [{}] from [{}]".format(year, str(month).zfill(2), 'FALSE', url))
                    continue
        print("{}-{} available [{}]".format(year, str(month).zfill(2), 'TRUE' if available else 'FALSE'))
        month_df = None
        for header_rows in ATO_XLS_HEADER_ROWS:
            month_df = pd.read_excel(year_month_file, skiprows=header_rows)
            if month_df.columns[0] == 'Country':
                month_df = month_df[month_df['Country'].isin(['USA', 'UK'])]
                for column in month_df.columns:
                    if isinstance(column, basestring) and column != 'Country':
                        if column[0].isdigit():
                            match = re.compile("(.*)-(.*)").match(column)
                            month_df.rename(columns={column: "{}-{}-{}".format(
                                year, str(list(calendar.month_abbr).index(match.group(2))).zfill(2), match.group(1).zfill(2)
                            )}, inplace=True)
                        else:
                            month_df.drop(column, axis=1, inplace=True)
                    elif isinstance(column, datetime.datetime):
                        month_df.rename(columns={column: column.strftime("{}-%m-%d".format(year))}, inplace=True)
                month_df = month_df.melt('Country', var_name='Date', value_name='Rate'). \
                    pivot_table('Rate', ['Date'], 'Country', aggfunc='first'). \
                    fillna(method='ffill').fillna(method='bfill').reset_index()
                month_df.rename(columns={'USA': 'USD/AUD', 'UK': 'GBP/AUD'}, inplace=True)
                month_df.index.name = None
                month_df.columns.name = None
                month_df['Source'] = 'ATO'
                month_df = month_df[['Source', 'Date', 'GBP/AUD', 'USD/AUD']]
                all_df = all_df.append(month_df, ignore_index=True, verify_integrity=True)
                print("{}-{} parsed [{}] with header rows [{}] and data points [{}]".
                      format(year, str(month).zfill(2), 'TRUE', header_rows, len(month_df)))
                break
        if month_df is not None:
            print("{}-{} processed [{}]".format(year, str(month).zfill(2), 'TRUE'))
        else:
            print("{}-{} processed [{}]".format(year, str(month).zfill(2), 'FALSE'))

for years in RBA_YEARS:
    available = False
    years_file = os.path.join(DATA_DIR_XLS, "rba_fx_{}.xls".format(years))
    if 'current' not in years and os.path.isfile(years_file):
        print("{} cached [{}]".format(years, 'TRUE'))
        available = True
    else:
        print("{} cached [{}]".format(years, 'FALSE'))
        url = RBA_URL.format(years)
        try:
            month_xls = urllib2.urlopen(urllib2.Request(url, headers=HTTP_HEADER),
                                        context=ssl._create_unverified_context())
            with open(years_file, 'wb') as output:
                output.write(month_xls.read())
            print("{} downloaded [{}] from [{}]".format(years, 'TRUE', url))
            available = True
        except:
            print("{} downloaded [{}] from [{}]".format(years, 'FALSE', url))
            continue
    print("{} available [{}]".format(years, 'TRUE' if available else 'FALSE'))
    years_df = pd.read_excel(years_file, skiprows=10)
    if years_df.columns[0] == 'Series ID':
        years_df = years_df.filter(['Series ID', 'FXRUSD', 'FXRUKPS']). \
            rename(columns={'Series ID': 'Date', 'FXRUSD': 'USD/AUD', 'FXRUKPS': 'GBP/AUD'})
        years_df['Date'] = years_df['Date'].dt.strftime("%Y-%m-%d").astype(str)
        years_df['Source'] = 'RBA'
        years_df = years_df[['Source', 'Date', 'GBP/AUD', 'USD/AUD']]
        all_df = all_df.append(years_df, ignore_index=True, verify_integrity=True)
        print("{} parsed [{}] with and data points [{}]".format(years, 'TRUE', len(years_df)))
if datetime.datetime.now().year > 2021:
    print("{}-{} processed [{}], update [RBA_YEARS]".format(2022, '01', 'FALSE'))

all_df = all_df.drop_duplicates(subset='Date', keep="first")
all_df['Date'] = pd.to_datetime(all_df['Date'])
all_df = all_df.set_index('Date').sort_index()
date_start = "{}/{}".format(all_df.index[0].year, str(all_df.index[0].month).zfill(2))
date_finish = "{}/{}".format(all_df.index[-1].year, str(all_df.index[-1].month).zfill(2))
print("{}-{} collated with rows [{}]".format(date_start, date_finish, len(all_df)))
all_df = all_df.reindex(pd.date_range(start=all_df.index[0], end=all_df.index[-1])).fillna(method='ffill').fillna(method='bfill')
all_df['Date'] = all_df.index.strftime("%Y-%m-%d")
all_df = all_df[['Source', 'Date', 'GBP/AUD', 'USD/AUD']]
print("{}-{} extrapolated with rows [{}]".format(date_start, date_finish, len(all_df)))
all_df.to_csv(os.path.join(DATA_DIR_CSV, "ato_fx_{}_{}.csv".
                           format(date_start.replace("/", "-"), date_finish.replace("/", "-"))), index=False)
Spread(DRIVE_SHEET).df_to_sheet(all_df, index=False, sheet='FX', start='A1', replace=True)
print("{}-{} uploaded with rows [{}]".format(date_start, date_finish, len(all_df)))
