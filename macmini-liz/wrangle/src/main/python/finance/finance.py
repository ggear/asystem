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
HTTP_HEADER = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
    'Accept-Encoding': 'none',
    'Accept-Language': 'en-US,en;q=0.8',
    'Connection': 'keep-alive'
}

DRIVE_RATES_URL = "https://docs.google.com/spreadsheets/d/10mcrUb5eMn4wz5t0e98-G2uN26v7Km5tyBui2sTkCe8"


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


def download_file(measurement_label, file_name, file_label, file_url, force=False):
    if not force and os.path.isfile(file_name):
        print("DEBUG [{}]: {} cached [{}]".format(measurement_label, file_label, 'TRUE'))
        available = True
    else:
        print("DEBUG [{}]: {} cached [{}]".format(measurement_label, file_label, 'FALSE'))
        try:
            month_xls = urllib2.urlopen(urllib2.Request(file_url, headers=HTTP_HEADER), context=ssl._create_unverified_context())
            with open(file_name, 'wb') as output:
                output.write(month_xls.read())
            print("DEBUG [{}]: {} downloaded [{}] from [{}]".format(measurement_label, file_label, 'TRUE', file_url))
            available = True
        except:
            print("DEBUG [{}]: {} downloaded [{}] from [{}]".format(measurement_label, file_label, 'FALSE', file_url))
    print("DEBUG [{}]: {} available [{}]".format(measurement_label, file_label, 'TRUE' if available else 'FALSE'))
    return available


def do_equity(profile_loaded):
    # TODO: Provide implementation
    print("DEBUG [Equity]: Not implement yet!")


INT_PERIODS = {'Yearly': 12, 'Five-Yearly': 5 * 12, 'Decennially': 10 * 12}
INT_RETAIL_URL = "https://www.rba.gov.au/statistics/tables/xls/f04hist.xls"
INT_INFLATION_URL = "https://www.rba.gov.au/statistics/tables/xls/g01hist.xls"
INT_DIR_DATA = os.path.abspath("{}/interest".format(os.path.dirname(os.path.realpath(__file__))))
INT_LINE_PROTOCOL = "interest,source={},type={},period={} {}="


def do_interest(profile_loaded):
    if not os.path.exists(INT_DIR_DATA):
        os.makedirs(INT_DIR_DATA)

    interest_df = pd.DataFrame()
    retail_file = os.path.join(INT_DIR_DATA, "retail.xls")
    if download_file("Retail", retail_file, "retail-f04", INT_RETAIL_URL):
        retail_raw_df = pd.read_excel(retail_file, skiprows=11, header=None)
        interest_df['Date'] = pd.to_datetime(retail_raw_df.iloc[:, [0]][0].dt.strftime('%Y-%m-01'))
        interest_df['Retail'] = retail_raw_df.iloc[:, [14]]
        interest_df = interest_df.set_index('Date')
        print("DEBUG [Retail]: {} to {} extrapolated with rows [{}]".format(
            interest_df.first_valid_index().strftime('%Y-%m'), interest_df.last_valid_index().strftime('%Y-%m'), len(interest_df)))

    inflation_file = os.path.join(INT_DIR_DATA, "inflation.xls")
    if download_file("Inflation", inflation_file, "inflation-g01", INT_INFLATION_URL):
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
        for int_period in INT_PERIODS:
            interest_df['{} {}'.format(int_rate, int_period)] = interest_df[int_rate].rolling(INT_PERIODS[int_period]).mean()
    interest_df = interest_df.fillna(0)
    print("DEBUG [Interest]: {} to {} extrapolated with rows [{}]".format(
        interest_df.first_valid_index().strftime('%Y-%m'), interest_df.last_valid_index().strftime('%Y-%m'), len(interest_df)))

    for int_rate in ['Retail', 'Inflation', 'Net']:
        print("\n".join(INT_LINE_PROTOCOL.format("RBA", "snapshot", "monthly", int_rate.lower()) +
                        interest_df[int_rate].map(str) +
                        " " + (pd.to_datetime(interest_df.index).astype(int) + 6 * 60 * 60 * 1000000000).map(str)))
        for int_period in INT_PERIODS:
            print("\n".join(INT_LINE_PROTOCOL.format("RBA", "mean", int_period.lower(), int_rate.lower()) +
                            interest_df["{} {}".format(int_rate, int_period)].map(str) +
                            " " + (pd.to_datetime(interest_df.index).astype(int) + 6 * 60 * 60 * 1000000000).map(str)))
    print("DEBUG [Interest]: {} to {} output with rows [{}]".format(
        interest_df.first_valid_index().strftime('%Y-%m'), interest_df.last_valid_index().strftime('%Y-%m'), len(interest_df)))


CCY_PAIRS = ['AUD/GBP', 'AUD/USD', 'AUD/SGD']
CCY_PERIODS = {'Daily': 1, 'Weekly': 7, 'Monthly': 30, 'Yearly': 365}
CCY_ATO_START_MONTH = 5
CCY_ATO_START_YEAR = 2016
CCY_ATO_FINISH_YEAR = 2020
CCY_ATO_XLS_HEADER_ROWS = [5, 3, 2, 1, 4, 0, 6]
CCY_ATO_URL_PREFIX = "https://www.ato.gov.au/uploadedFiles/Content/TPALS/downloads/"
CCY_RBA_URL = "https://www.rba.gov.au/statistics/tables/xls-hist/{}.xls"
CCY_LINE_PROTOCOL = "currency,source={},type={},period={} {}="
CCY_DIR_DATA = os.path.abspath("{}/currency".format(os.path.dirname(os.path.realpath(__file__))))
CCY_ATO_URL_SUFFIX = [
    "{}_{}_daily_rates.xlsx",
    "{}_{}_daily_input.xlsx",
    "{}{}dailyinput.xlsx",
    "{}-{}-daily-input.xlsx",
    "{1}_{0}_daily_input.xlsx",
    "{1}_{0}_Daily_%20input.xlsx",
    "{}%20{}%20daily%20input.xlsx",
    "{}%20{}%20daily%20input.xls.xlsx"
]
CCY_RBA_YEARS = [
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


def do_currency(profile_loaded):
    if not os.path.exists(CCY_DIR_DATA):
        os.makedirs(CCY_DIR_DATA)

    rba_df = pd.DataFrame()
    ato_df = pd.DataFrame()
    merged_df = pd.DataFrame()

    for year in range(CCY_ATO_START_YEAR, CCY_ATO_FINISH_YEAR):
        for month in range(1 if year != CCY_ATO_START_YEAR else CCY_ATO_START_MONTH,
                           13 if year < datetime.datetime.now().year else datetime.datetime.now().month):
            month_string = datetime.date(2000, month, 1).strftime('%B')
            year_month_file = os.path.join(CCY_DIR_DATA, "ato_fx_{}-{}.xls".format(year, str(month).zfill(2)))
            for url_suffix in CCY_ATO_URL_SUFFIX:
                if download_file("Currency", year_month_file, "{}-{}".format(year, str(month).zfill(2)),
                                 (CCY_ATO_URL_PREFIX + url_suffix).format(month_string, year)):
                    break
            for header_rows in CCY_ATO_XLS_HEADER_ROWS:
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
                    ato_df = ato_df[['Source', 'Date'] + CCY_PAIRS]
                    merged_df = merged_df.append(ato_df, ignore_index=True, verify_integrity=True)
                    print("DEBUG [Currency]: {}-{} parsed [{}] with header rows [{}] and data points [{}]".
                          format(year, str(month).zfill(2), 'TRUE', header_rows, len(ato_df)))
                    break
            if ato_df is not None:
                print("DEBUG [Currency]: {}-{} processed [{}]".format(year, str(month).zfill(2), 'TRUE'))
            else:
                print("DEBUG [Currency]: {}-{} processed [{}]".format(year, str(month).zfill(2), 'FALSE'))

    for years in CCY_RBA_YEARS:
        years_months = (years.replace("-", "-01 to ") + ("2021-01" if years.endswith("current") else "-12")).replace("current", "")
        years_file = os.path.join(CCY_DIR_DATA, "rba_fx_{}.xls".format(years))
        download_file("Currency", years_file, years_months, CCY_RBA_URL.format(years), force='current' in years)
        rba_itr_df = pd.read_excel(years_file, skiprows=10)
        if rba_itr_df.columns[0] == 'Series ID':
            rba_itr_df = rba_itr_df.filter(['Series ID', 'FXRUSD', 'FXRUKPS', 'FXRSD']). \
                rename(columns={'Series ID': 'Date', 'FXRUSD': 'AUD/USD', 'FXRUKPS': 'AUD/GBP', 'FXRSD': 'AUD/SGD'})
            rba_itr_df['Date'] = rba_itr_df['Date'].dt.strftime("%Y-%m-%d").astype(str)
            rba_itr_df['Source'] = 'RBA'
            rba_itr_df = rba_itr_df[['Source', 'Date'] + CCY_PAIRS]
            rba_df = rba_df.append(rba_itr_df, ignore_index=True, verify_integrity=True)
            print("DEBUG [Currency]: {} parsed [{}] with and data points [{}]".format(years_months, 'TRUE', len(rba_itr_df)))

    if datetime.datetime.now().year > 2021:
        print("DEBUG [Currency]: {}-{} processed [{}], update [RBA_YEARS]".format(2022, '01', 'FALSE'))

    merged_df = rba_df.append(ato_df, ignore_index=True, verify_integrity=True)

    def extrapolate(data_df):
        data_df = data_df.drop_duplicates(subset='Date', keep="first").copy()
        data_df['Date'] = pd.to_datetime(data_df['Date'])
        data_df = data_df.set_index('Date').sort_index()
        date_start = "{}-{}".format(data_df.index[0].year, str(data_df.index[0].month).zfill(2))
        date_finish = "{}-{}".format(data_df.index[-1].year, str(data_df.index[-1].month).zfill(2))
        print("DEBUG [Currency]: {} to {} collated with rows [{}]".format(date_start, date_finish, len(data_df)))
        for fx_pair in CCY_PAIRS:
            data_df = data_df[~data_df[fx_pair].isin(['Closed', 'CLOSED'])]
        data_df = data_df.reindex(
            pd.date_range(start=data_df.index[0], end=data_df.index[-1])).fillna(method='ffill').fillna(method='bfill')
        data_df['Date'] = data_df.index.strftime("%Y-%m-%d")
        data_df = data_df[['Source', 'Date'] + CCY_PAIRS]
        for fx_pair in CCY_PAIRS:
            for fx_period in CCY_PERIODS:
                data_df['{} {}'.format(fx_pair, fx_period)] = (data_df[fx_pair].pct_change(CCY_PERIODS[fx_period])) * 100
        data_df = data_df.fillna(0)
        print("DEBUG [Currency]: {} to {} extrapolated with rows [{}]".format(date_start, date_finish, len(data_df)))
        return date_start, date_finish, data_df

    merged_tupple = extrapolate(merged_df)
    Spread(DRIVE_RATES_URL).df_to_sheet(merged_tupple[2], index=False, sheet='FX', start='A1', replace=True)
    print("DEBUG [Currency]: {} to {} uploaded to Drive with rows [{}]".format(merged_tupple[0], merged_tupple[1], len(merged_tupple[2])))

    rba_tupple = extrapolate(rba_df)
    for fx_pair in CCY_PAIRS:
        print("\n".join(CCY_LINE_PROTOCOL.format("RBA", "snapshot", "daily", fx_pair) +
                        rba_tupple[2][fx_pair].map(str) +
                        " " + (pd.to_datetime(rba_tupple[2]['Date']).astype(int) + 6 * 60 * 60 * 1000000000).map(str)))
        for fx_period in CCY_PERIODS:
            print("\n".join(CCY_LINE_PROTOCOL.format("RBA", "delta", fx_period.lower(), fx_pair) +
                            rba_tupple[2]["{} {}".format(fx_pair, fx_period)].map(str) +
                            " " + (pd.to_datetime(rba_tupple[2]['Date']).astype(int) + 6 * 60 * 60 * 1000000000).map(str)))
    print("DEBUG [Currency]: {} to {} output with rows [{}]".format(rba_tupple[0], rba_tupple[1], len(rba_tupple[2])))


if __name__ == "__main__":
    time_start = int(time.time())
    print("DEBUG [Finance]: Started processing")
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
        do_equity(profile)
        do_interest(profile)
        do_currency(profile)

    print("DEBUG [Finance]: Completed in [{}] secs".format(int(time.time()) - time_start))
