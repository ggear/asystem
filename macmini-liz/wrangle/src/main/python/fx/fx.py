from __future__ import print_function

import calendar
import datetime
import os
import re
import ssl
import sys
import time
import traceback
import urllib2

import pandas as pd
from gspread_pandas import Spread

STACKTRACE_REFERENCE_LIMIT = 1

DEFAULT_PROFILE_PATH = "../../resources/config/.profile"


def load_profile(profile_file):
    profile = {}
    for profile_line in profile_file:
        profile_line = profile_line.replace("export ", "").rstrip()
        if "=" not in profile_line:
            continue
        if profile_line.startswith("#"):
            continue
        profile_key, profile_value = profile_line.split("=", 1)
        profile[profile_key] = profile_value
    profile["INFLUXDB_HOST"] = os.environ['INFLUXDB_HOST'] if "INFLUXDB_HOST" in os.environ else "192.168.1.10"
    profile["INFLUXDB_PORT"] = os.environ['INFLUXDB_PORT'] if "INFLUXDB_PORT" in os.environ else "8086"
    return profile


DATA_DIR_XLS = os.path.abspath("{}/xls".format(os.path.dirname(os.path.realpath(__file__))))
DATA_DIR_CSV = os.path.abspath("{}/csv".format(os.path.dirname(os.path.realpath(__file__))))

FX_PAIRS = ['AUD/GBP', 'AUD/USD', 'AUD/SGD']
FX_PERIODS = {'Daily': 1, 'Weekly': 7, 'Monthly': 30, 'Yearly': 365}

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

INFLUX_LINEPROTOCOL_VALUE = "fx,source={},type={},period={} {}="

if __name__ == "__main__":

    time_start = int(time.time())
    print("DEBUG: Started processing")

    profile_path = DEFAULT_PROFILE_PATH if len(sys.argv) == 1 else sys.argv[1]
    profile = None
    try:
        with open(profile_path, 'r') as profile_file:
            profile = load_profile(profile_file)
    except Exception as exception:
        print("Error processing profile - ", end="", file=sys.stderr)
        traceback.print_exc(limit=STACKTRACE_REFERENCE_LIMIT)
        sys.exit(1)
    if profile is not None:

        if not os.path.exists(DATA_DIR_XLS):
            os.makedirs(DATA_DIR_XLS)
        if not os.path.exists(DATA_DIR_CSV):
            os.makedirs(DATA_DIR_CSV)

        rba_df = pd.DataFrame()
        ato_df = pd.DataFrame()
        merged_df = pd.DataFrame()

        for year in range(ATO_START_YEAR, ATO_FINISH_YEAR):
            for month in range(1 if year != ATO_START_YEAR else ATO_START_MONTH,
                               13 if year < datetime.datetime.now().year else datetime.datetime.now().month):
                month_string = datetime.date(2000, month, 1).strftime('%B')
                year_month_file = os.path.join(DATA_DIR_XLS, "ato_fx_{}-{}.xls".format(year, str(month).zfill(2)))
                available = False
                if os.path.isfile(year_month_file):
                    print("DEBUG: {}-{} cached [{}]".format(year, str(month).zfill(2), 'TRUE'))
                    available = True
                else:
                    print("DEBUG: {}-{} cached [{}]".format(year, str(month).zfill(2), 'FALSE'))
                    for suffix in ATO_URL_SUFFIX:
                        url = (ATO_URL_PREFIX + suffix).format(month_string, year)
                        try:
                            month_xls = urllib2.urlopen(urllib2.Request(url, headers=HTTP_HEADER), context=ssl._create_unverified_context())
                            with open(year_month_file, 'wb') as output:
                                output.write(month_xls.read())
                            print("DEBUG: {}-{} downloaded [{}] from [{}]".format(year, str(month).zfill(2), 'TRUE', url))
                            available = True
                            break
                        except:
                            print("DEBUG: {}-{} downloaded [{}] from [{}]".format(year, str(month).zfill(2), 'FALSE', url))
                            continue
                print("DEBUG: {}-{} available [{}]".format(year, str(month).zfill(2), 'TRUE' if available else 'FALSE'))
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
                        ato_df = ato_df[['Source', 'Date'] + FX_PAIRS]
                        merged_df = merged_df.append(ato_df, ignore_index=True, verify_integrity=True)
                        print("DEBUG: {}-{} parsed [{}] with header rows [{}] and data points [{}]".
                              format(year, str(month).zfill(2), 'TRUE', header_rows, len(ato_df)))
                        break
                if ato_df is not None:
                    print("DEBUG: {}-{} processed [{}]".format(year, str(month).zfill(2), 'TRUE'))
                else:
                    print("DEBUG: {}-{} processed [{}]".format(year, str(month).zfill(2), 'FALSE'))

        for years in RBA_YEARS:
            available = False
            years_months = (years.replace("-", "-01 to ") + ("2021-01" if years.endswith("current") else "-12")).replace("current", "")
            years_file = os.path.join(DATA_DIR_XLS, "rba_fx_{}.xls".format(years))
            if 'current' not in years and os.path.isfile(years_file):
                print("DEBUG: {} cached [{}]".format(years_months, 'TRUE'))
                available = True
            else:
                print("DEBUG: {} cached [{}]".format(years_months, 'FALSE'))
                url = RBA_URL.format(years)
                try:
                    month_xls = urllib2.urlopen(urllib2.Request(url, headers=HTTP_HEADER), context=ssl._create_unverified_context())
                    with open(years_file, 'wb') as output:
                        output.write(month_xls.read())
                    print("DEBUG: {} downloaded [{}] from [{}]".format(years_months, 'TRUE', url))
                    available = True
                except:
                    print("DEBUG: {} downloaded [{}] from [{}]".format(years_months, 'FALSE', url))
                    continue
            print("DEBUG: {} available [{}]".format(years_months, 'TRUE' if available else 'FALSE'))
            rba_itr_df = pd.read_excel(years_file, skiprows=10)
            if rba_itr_df.columns[0] == 'Series ID':
                rba_itr_df = rba_itr_df.filter(['Series ID', 'FXRUSD', 'FXRUKPS', 'FXRSD']). \
                    rename(columns={'Series ID': 'Date', 'FXRUSD': 'AUD/USD', 'FXRUKPS': 'AUD/GBP', 'FXRSD': 'AUD/SGD'})
                rba_itr_df['Date'] = rba_itr_df['Date'].dt.strftime("%Y-%m-%d").astype(str)
                rba_itr_df['Source'] = 'RBA'
                rba_itr_df = rba_itr_df[['Source', 'Date'] + FX_PAIRS]
                rba_df = rba_df.append(rba_itr_df, ignore_index=True, verify_integrity=True)
                print("DEBUG: {} parsed [{}] with and data points [{}]".format(years_months, 'TRUE', len(rba_itr_df)))

        if datetime.datetime.now().year > 2021:
            print("DEBUG: {}-{} processed [{}], update [RBA_YEARS]".format(2022, '01', 'FALSE'))

        merged_df = rba_df.append(ato_df, ignore_index=True, verify_integrity=True)


        def extrapolate(data_df):
            data_df = data_df.drop_duplicates(subset='Date', keep="first").copy()
            data_df['Date'] = pd.to_datetime(data_df['Date'])
            data_df = data_df.set_index('Date').sort_index()
            date_start = "{}-{}".format(data_df.index[0].year, str(data_df.index[0].month).zfill(2))
            date_finish = "{}-{}".format(data_df.index[-1].year, str(data_df.index[-1].month).zfill(2))
            print("DEBUG: {} to {} collated with rows [{}]".format(date_start, date_finish, len(data_df)))
            for fx_pair in FX_PAIRS:
                data_df = data_df[~data_df[fx_pair].isin(['Closed', 'CLOSED'])]
            data_df = data_df.reindex(
                pd.date_range(start=data_df.index[0], end=data_df.index[-1])).fillna(method='ffill').fillna(method='bfill')
            data_df['Date'] = data_df.index.strftime("%Y-%m-%d")
            data_df = data_df[['Source', 'Date'] + FX_PAIRS]
            for fx_pair in FX_PAIRS:
                for fx_period in FX_PERIODS:
                    data_df['{} {}'.format(fx_pair, fx_period)] = (data_df[fx_pair].pct_change(FX_PERIODS[fx_period])) * 100
            data_df = data_df.fillna(0)
            print("DEBUG: {} to {} extrapolated with rows [{}]".format(date_start, date_finish, len(data_df)))
            return (date_start, date_finish, data_df)


        merged_tupple = extrapolate(merged_df)
        Spread(DRIVE_SHEET).df_to_sheet(merged_tupple[2], index=False, sheet='FX', start='A1', replace=True)
        print("DEBUG: {} to {} uploaded to Drive with rows [{}]".format(merged_tupple[0], merged_tupple[1], len(merged_tupple[2])))

        rba_tupple = extrapolate(rba_df)
        for fx_pair in FX_PAIRS:
            print("\n".join(INFLUX_LINEPROTOCOL_VALUE.format("RBA", "snapshot", "daily", fx_pair) +
                            rba_tupple[2][fx_pair].map(str) +
                            " " + (pd.to_datetime(rba_tupple[2]['Date']).astype(int) + 6 * 60 * 60 * 1000000000).map(str)))
            for fx_period in FX_PERIODS:
                print("\n".join(INFLUX_LINEPROTOCOL_VALUE.format("RBA", "delta", fx_period.lower(), fx_pair) +
                                rba_tupple[2]["{} {}".format(fx_pair, fx_period)].map(str) +
                                " " + (pd.to_datetime(rba_tupple[2]['Date']).astype(int) + 6 * 60 * 60 * 1000000000).map(str)))
        print("DEBUG: {} to {} uploaded to InfluxDB with rows [{}]".format(rba_tupple[0], rba_tupple[1], len(rba_tupple[2])))

    print("DEBUG: Completed in [{}] secs".format(int(time.time()) - time_start))
