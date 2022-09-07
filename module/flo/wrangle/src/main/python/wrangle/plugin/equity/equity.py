import calendar
import datetime
import os
from collections import OrderedDict
from datetime import datetime
from warnings import simplefilter

import numpy as np
import pandas as pd
import pdftotext
import pytz

from .. import library

simplefilter(action="ignore", category=pd.errors.PerformanceWarning)

STATUS_FAILURE = "failure"
STATUS_SKIPPED = "skipped"
STATUS_SUCCESS = "success"

STATEMENT_CURRENCIES = ["GBP", "USD", "SGD"]
STATEMENT_ATTRIBUTES = ("Date", "Type", "Owner", "Currency", "Rate", "Units", "Value")

STOCK = OrderedDict([
    ('AORD', {
        "start": "1985-01",
        "end of day": "16:00",
        "prefix": "^",
        "exchange": "",
    }),
    ('WDS', {
        "start": "2009-01",
        "end of day": "16:00",
        "prefix": "",
        "exchange": "AX",
    }),
    ('SIG', {
        "start": "2006-01",
        "end of day": "16:00",
        "prefix": "",
        "exchange": "AX",
    }),
    ('OZL', {
        "start": "2009-01",
        "end of day": "16:00",
        "prefix": "",
        "exchange": "AX",
    }),
    ('VAS', {
        "start": "2010-01",
        "end of day": "16:00",
        "prefix": "",
        "exchange": "AX",
    }),
    ('VHY', {
        "start": "2011-01",
        "end of day": "16:00",
        "prefix": "",
        "exchange": "AX",
    }),
    ('VAE', {
        "start": "2016-01",
        "end of day": "16:00",
        "prefix": "",
        "exchange": "AX",
    }),
    ('VDHG', {
        "start": "2018-01",
        "end of day": "16:00",
        "prefix": "",
        "exchange": "AX",
    }),
    ('CLNE', {
        "start": "2021-04",
        "end of day": "16:00",
        "prefix": "",
        "exchange": "AX",
    }),
    ('IAF', {
        "start": "2012-04",
        "end of day": "16:00",
        "prefix": "",
        "exchange": "AX",
    }),
    ('GOLD', {
        "start": "2008-01",
        "end of day": "16:00",
        "prefix": "",
        "exchange": "AX",
    }),
    ('ERTH', {
        "start": "2021-04",
        "end of day": "16:00",
        "prefix": "",
        "exchange": "AX",
    }),
])

DIMENSIONS = [
    "Price Open",
    "Price High",
    "Price Low",
    "Price Close",
    "Market Volume",
    "Paid Dividends",
    "Stock Splits",
    "Currency Rate Base",
    "Currency Base",
]

DRIVE_URL = "https://docs.google.com/spreadsheets/d/1qMllD2sPCPYA-URgyo7cp6aXogJcYNCKQ7Dw35_PCgM"
DRIVE_URL_PORTFOLIO = "https://docs.google.com/spreadsheets/d/1Kf9-Gk7aD4aBdq2JCfz5zVUMWAtvJo2ZfqmSQyo8Bjk"


class Equity(library.Library):

    def _run(self):
        new_data = False
        equity_df = pd.DataFrame()
        equity_delta_df = pd.DataFrame()
        stock_files = {}
        statement_files = {}
        if not library.test(library.WRANGLE_DISABLE_FILE_DOWNLOAD):
            for stock in STOCK:
                today = datetime.today()
                stock_start = datetime.strptime(STOCK[stock]["start"], '%Y-%m')
                for year in range(stock_start.year, today.year + 1):
                    if year == today.year:
                        for month in range(1, today.month + 1):
                            if year != stock_start.year or month >= stock_start.month:
                                file_name = "{}/Yahoo_{}_{}-{:02}.csv".format(self.input, stock, year, month)
                                stock_files[file_name] = self.stock_download(
                                    file_name,
                                    "{}{}{}{}".format(STOCK[stock]["prefix"], stock,
                                                      '.' if STOCK[stock]["exchange"] != "" else '', STOCK[stock]["exchange"]),
                                    "{}-{:02}-01".format(year, month),
                                    "{}-{:02}-{:02}".format(
                                        year,
                                        month,
                                        calendar.monthrange(year, month)[1]),
                                    STOCK[stock]["end of day"], check=year == today.year and month == today.month)
                    else:
                        file_name = "{}/Yahoo_{}_{}.csv".format(self.input, stock, year)
                        stock_files[file_name] = self.stock_download(
                            file_name,
                            "{}{}{}{}".format(STOCK[stock]["prefix"], stock,
                                              '.' if STOCK[stock]["exchange"] != "" else '', STOCK[stock]["exchange"]),
                            "{}-{:02}-01".format(year, 1),
                            "{}-{:02}-{:02}".format(
                                year,
                                12,
                                31),
                            STOCK[stock]["end of day"], check=False)
            files_cached = self.get_counter(library.CTR_SRC_SOURCES, library.CTR_ACT_CACHED)
            files_downloaded = self.get_counter(library.CTR_SRC_SOURCES, library.CTR_ACT_DOWNLOADED)
            files = self.drive_sync(self.input_drive, self.input)
            self.add_counter(library.CTR_SRC_SOURCES, library.CTR_ACT_CACHED, -1 * (files_cached + files_downloaded))
            for file_name in files:
                if os.path.basename(file_name).startswith("58861"):
                    statement_files[file_name] = files[file_name]
                elif os.path.basename(file_name).startswith("Yahoo"):
                    if files[file_name][0] and (library.test(library.WRANGLE_DISABLE_DATA_DELTA) or files[file_name][1]):
                        stock_files[file_name] = files[file_name]
            new_data = library.test(library.WRANGLE_DISABLE_DATA_DELTA) or \
                       (all([status[0] for status in list(stock_files.values())]) and any(
                           [status[1] for status in list(stock_files.values())])) or \
                       (all([status[0] for status in list(statement_files.values())]) and any(
                           [status[1] for status in list(statement_files.values())]))
        elif library.test(library.WRANGLE_DISABLE_DATA_DELTA):
            stock_files = self.file_list(self.input, "Yahoo")
            statement_files = self.file_list(self.input, "58861")
            new_data = stock_files or statement_files
        stocks_df = {}
        for stock_file_name in stock_files:
            if stock_files[stock_file_name][0]:
                if library.test(library.WRANGLE_DISABLE_DATA_DELTA) or stock_files[stock_file_name][1]:
                    try:
                        stock_ticker = os.path.basename(stock_file_name).split('_')[1]
                        stock_df = pd.read_csv(stock_file_name) \
                            .add_prefix("{} ".format(stock_ticker)).rename({"{} Date".format(stock_ticker): 'Date'}, axis=1)
                        stock_df["{} Currency Rate Base".format(stock_ticker)] = 1.0
                        stock_df["{} Currency Base".format(stock_ticker)] = "AUD"
                        stock_df.columns = ["Date"] + ["{} ".format(stock_ticker) + column for column in DIMENSIONS]
                        stock_df = stock_df.set_index('Date')
                        if stock_ticker in stocks_df:
                            stocks_df[stock_ticker] = pd.concat([stocks_df[stock_ticker], stock_df], sort=True)  # type: ignore
                        else:
                            stocks_df[stock_ticker] = stock_df
                        self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                    except Exception as exception:
                        self.print_log("Unexpected error processing file [{}]".format(stock_file_name), exception)
                        self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
                else:
                    self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED)
            else:
                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
        statement_data = {}
        for statement_file_name in statement_files:
            if statement_files[statement_file_name][0]:
                if library.test(library.WRANGLE_DISABLE_DATA_DELTA) or statement_files[statement_file_name][1]:
                    with open(statement_file_name, "rb") as statement_file:
                        statement_data[statement_file_name] = {}
                        try:
                            statement_date = None
                            statement_type = None
                            statement_owner = None
                            statement_rates = {}
                            statement_data[statement_file_name]['Status'] = STATUS_FAILURE
                            statement_data[statement_file_name]["Errors"] = []
                            statement_data[statement_file_name]["Positions"] = {}
                            statement_data[statement_file_name]['Parse'] = ""
                            statement_pages = pdftotext.PDF(statement_file)
                            page_index = 0
                            while page_index < len(statement_pages):
                                line_index = 0
                                statement_lines = statement_pages[page_index].split("\n")
                                if page_index == 0:
                                    if len(statement_lines) > 1 and (
                                            statement_lines[0].strip().startswith("Consolidated Statement") or
                                            statement_lines[0].strip().startswith("Statement of")
                                    ):
                                        statement_data[statement_file_name]['Status'] = STATUS_SUCCESS
                                    elif len(statement_lines) > 1 and "Administration Services" in statement_lines[0]:
                                        statement_data[statement_file_name]['Status'] = STATUS_SKIPPED
                                    else:
                                        statement_data[statement_file_name]["Errors"].append("File missing required heading")
                                while line_index < len(statement_lines):
                                    statement_data[statement_file_name]['Parse'] += "File [{}]: Page [{:02d}]: Line [{:02d}]:  " \
                                        .format(os.path.basename(statement_file_name), page_index, line_index)
                                    statement_line = statement_lines[line_index].strip()
                                    statement_tokens = statement_line.split()
                                    token_index = 0
                                    while token_index < len(statement_tokens):
                                        statement_data[statement_file_name]['Parse'] += "{:02d}:{} " \
                                            .format(token_index, statement_tokens[token_index])
                                        token_index += 1
                                    statement_data[statement_file_name]['Parse'] += "\n"
                                    if statement_data[statement_file_name]['Status'] == STATUS_SUCCESS:
                                        if page_index == 0:
                                            if statement_line.strip().startswith("Account name"):
                                                if "Jane" in statement_line and "Gear" in statement_line:
                                                    statement_type = "Fund "
                                                    statement_owner = "Joint"
                                                elif "Jane" in statement_line and "Gear" not in statement_line:
                                                    statement_type = "Equity "
                                                    statement_owner = "Jane"
                                                else:
                                                    statement_data[statement_file_name]['Status'] = STATUS_FAILURE
                                                    statement_data[statement_file_name]["Errors"] \
                                                        .append("Could not determine statement type or owner from line [{}]"
                                                                .format(statement_line))
                                            if statement_line.startswith("Statement date"):
                                                statement_date_str = statement_tokens[2]
                                                if len(statement_date_str) == 9:
                                                    statement_date = datetime.strptime(statement_tokens[2], '%d-%b-%y')
                                                elif len(statement_date_str) == 11:
                                                    statement_date = datetime.strptime(statement_tokens[2], '%d-%b-%Y')
                                                else:
                                                    raise Exception("Could not parse date [{}]".format(statement_date_str))
                                            if statement_type:
                                                for currency in STATEMENT_CURRENCIES:
                                                    if statement_line.startswith(currency):
                                                        statement_rates[currency] = \
                                                            float(statement_tokens[4].replace(',', ''))
                                        if statement_type:
                                            for indexes in [
                                                (2, "Situations", STATEMENT_CURRENCIES, 5, 10, 2, 6),
                                                (2, "Situations", STATEMENT_CURRENCIES, 8, 13, 2, 6),
                                                (3, "Situations", STATEMENT_CURRENCIES, 5, 9, 2, 6),
                                                (2, "Shares", ["USD"], 2, 7),
                                                (3, "Shares", ["USD"], 2, 6),
                                            ]:
                                                if page_index == indexes[0] and indexes[1] in statement_line:
                                                    for currency in indexes[2]:
                                                        if indexes[1] == "Shares" or currency in statement_line:
                                                            try:
                                                                statement_position = {
                                                                    "Date": statement_date,
                                                                    "Type": statement_type.strip(),
                                                                    "Owner": statement_owner,
                                                                    "Currency": currency,
                                                                    "Rate": statement_rates[currency],
                                                                    "Units": float(statement_tokens
                                                                                   [indexes[3]].replace(',', '')),
                                                                    "Value": float(statement_tokens
                                                                                   [indexes[4]].replace(',', ''))
                                                                }
                                                                if indexes[1] == "Situations":
                                                                    if line_index < (len(statement_lines) - 1) and \
                                                                            statement_lines[line_index + 1].strip().startswith("PCC"):
                                                                        currency = statement_lines[line_index + 1].strip().split()[
                                                                            indexes[5]]
                                                                    else:
                                                                        currency = statement_tokens[indexes[6]]
                                                                statement_position["Ticker"] = \
                                                                    'MCK' if statement_owner == 'Jane' \
                                                                             and currency == 'USD' else \
                                                                        'MUS' if statement_owner == 'Joint' \
                                                                                 and currency == 'USD' else \
                                                                            'MUK' if statement_owner == 'Joint' \
                                                                                     and currency == 'GBP' else \
                                                                                'MSG' if statement_owner == 'Joint' \
                                                                                         and currency == 'SGD' else \
                                                                                    'UNKOWN'
                                                                statement_data[statement_file_name]["Positions"] \
                                                                    [str(statement_type + currency)] = statement_position
                                                            except (Exception,):
                                                                pass
                                    line_index += 1
                                page_index += 1
                            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                        except Exception as exception:
                            statement_data[statement_file_name]['Status'] = STATUS_FAILURE
                            statement_data[statement_file_name]["Errors"].append(
                                "Statement parse failed with exception [{}: {}]".format(type(exception).__name__, exception))
                            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
                    if statement_data[statement_file_name]['Status'] == STATUS_SUCCESS:
                        statement_positions = statement_data[statement_file_name]["Positions"]
                        for statement_position in list(statement_positions.values()):
                            if len(statement_positions) == 0 or not all(key in statement_position for key in STATEMENT_ATTRIBUTES):
                                statement_data[statement_file_name]['Status'] = STATUS_FAILURE
                                statement_data[statement_file_name]["Errors"] \
                                    .append("Statement parse failed to resolve all keys {} in {}"
                                            .format(STATEMENT_ATTRIBUTES, statement_position))
                else:
                    self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED)
        try:
            if new_data:
                statements_positions = []
                self.print_log("Data has [{}] statements pre processing".format(len(statement_data)))
                for file_name in statement_data:
                    if statement_data[file_name]['Status'] == STATUS_SUCCESS:
                        statement_position = statement_data[file_name]["Positions"]
                        statements_positions.extend(list(statement_position.values()))
                        self.print_log("File [{}] processed as [{}] with positions {}"
                                       .format(os.path.basename(file_name), STATUS_SUCCESS, list(statement_position.keys())))
                    elif statement_data[file_name]['Status'] == STATUS_SKIPPED:
                        self.print_log("File [{}] processed as [{}]".format(os.path.basename(file_name), STATUS_SKIPPED))
                    else:
                        self.print_log("File [{}] processed as [{}] at parsing point:".format(os.path.basename(file_name), STATUS_FAILURE))
                        self.print_log(statement_data[file_name]["Parse"].split("\n"))
                        self.print_log("File [{}] processed as [{}] with errors:".format(os.path.basename(file_name), STATUS_FAILURE))
                        if not statement_data[file_name]["Errors"]:
                            statement_data[file_name]["Errors"] = ["<NONE>"]
                        error_index = 0
                        while error_index < len(statement_data[file_name]["Errors"]):
                            self.print_log(" {:2d}: {}".format(error_index, statement_data[file_name]["Errors"][error_index]))
                            error_index += 1
                statement_df = pd.DataFrame(statements_positions)
                if len(statement_df) > 0:
                    statement_df["Price"] = statement_df["Value"] / statement_df["Units"]
                    statement_df['Rate'] = 1.0 / statement_df['Rate']
                    statement_df['Zero'] = 0.0
                    statement_df = statement_df.set_index('Date')
                    statement_df = pd.concat([
                        statement_df.pivot(columns='Ticker', values='Price').add_suffix(' Price Open'),
                        statement_df.pivot(columns='Ticker', values='Price').add_suffix(' Price High'),
                        statement_df.pivot(columns='Ticker', values='Price').add_suffix(' Price Low'),
                        statement_df.pivot(columns='Ticker', values='Price').add_suffix(' Price Close'),
                        statement_df.pivot(columns='Ticker', values='Zero').add_suffix(' Market Volume'),
                        statement_df.pivot(columns='Ticker', values='Zero').add_suffix(' Paid Dividends'),
                        statement_df.pivot(columns='Ticker', values='Zero').add_suffix(' Stock Splits'),
                        statement_df.pivot(columns='Ticker', values='Rate').add_suffix(' Currency Rate Base'),
                        statement_df.pivot(columns='Ticker', values='Currency').add_suffix(' Currency Base'),
                    ], axis=1)
                    statement_df.index = pd.to_datetime(statement_df.index)  # type: ignore
                    statement_df = statement_df.resample('D').interpolate(limit_direction='both', limit_area='inside') \
                        .replace('', np.nan).ffill()
                    for column in statement_df.columns:
                        if column.endswith('Currency Base'):
                            statement_df[column] = statement_df[column].loc[statement_df[column].first_valid_index()]
                self.print_log("Data has [{}] statement rows post processing".format(len(statement_df)))
                for stock in STOCK:
                    if stock in stocks_df:
                        equity_df = pd.concat([equity_df, stocks_df[stock][~stocks_df[stock].index.duplicated()]], axis=1, sort=True)
                equity_df.index = pd.to_datetime(equity_df.index)  # type: ignore
                equity_df = equity_df.resample('D').ffill().replace('', np.nan).ffill()
                equity_df = pd.concat([equity_df, statement_df], axis=1, sort=True)
                equity_df.index = pd.to_datetime(equity_df.index)
                equity_df = equity_df[~equity_df.index.duplicated(keep='last')]
                equity_df.index = pd.to_datetime(equity_df.index)
                equity_df = equity_df.sort_index(axis=1)
                self.print_log("Data has [{}] rows post statement and stock merge".format(len(equity_df)))
                equity_df_manual = self.sheet_read(DRIVE_URL, "Equity_manual",
                                                   read_cache=library.test(library.WRANGLE_DISABLE_FILE_DOWNLOAD),
                                                   sheet_params={"sheet": "Manual", "index": None, "start_row": 1})
                equity_df_manual.index = pd.to_datetime(equity_df_manual["Date"])
                del equity_df_manual["Date"]
                equity_df_manual = equity_df_manual.apply(pd.to_numeric)

                equity_df_manual = equity_df_manual.resample('D').interpolate(limit_direction='both', limit_area='inside') \
                    .replace('', np.nan).ffill()

                equity_df.update(equity_df_manual)
                equity_df = equity_df.sort_index(axis=1).interpolate(limit_direction='both', limit_area='inside') \
                    .replace('', np.nan).ffill()
                self.print_log("Data has [{}] rows post sheet merge".format(len(equity_df)))
        except Exception as exception:
            self.print_log("Unexpected error processing equity dataframe", exception)
            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED,
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED) +
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED) -
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED))
        try:
            def aggregate_function(data_df):
                return data_df.apply(pd.to_numeric, errors='ignore').round(4)

            equity_delta_df, equity_current_df, _ = self.state_cache(equity_df, aggregate_function)
            if len(equity_delta_df):
                tickers = [ticker.replace(" Price Close", "") for ticker in equity_current_df.columns if ticker.endswith("Price Close")]
                equity_subset_df = equity_current_df[[ticker + dimension for ticker in tickers for dimension in [
                    " Price Close",
                    " Currency Rate Base",
                ]]]
                equity_subset_df.insert(0, "Date", equity_subset_df.index.strftime('%Y-%m-%d'))
                equity_subset_df = equity_subset_df[equity_subset_df['Date'] > '2007-01-01'].sort_index(ascending=False)
                self.sheet_write(equity_subset_df, DRIVE_URL, {'index': False, 'sheet': 'History', 'start': 'A1', 'replace': True})
                self.print_log("Data has [{}] columns and [{}] rows pre enrichment"
                               .format(len(equity_current_df.columns), len(equity_current_df)))
                equity_subset_df = equity_current_df.copy().dropna(axis=1, how='all')
                columns_numeric = []
                for column in equity_subset_df.columns:
                    if "Currency Base" not in column:
                        columns_numeric.append(column)
                equity_subset_df[columns_numeric] = equity_subset_df[columns_numeric].apply(pd.to_numeric)
                column = [(ticker + " " + column) for column in
                          [dimension_target for dimension_target in DIMENSIONS if dimension_target not in
                           ["Market Volume", "Paid Dividends", "Stock Splits"]] for ticker in tickers]
                equity_subset_df.loc[:, column] = equity_subset_df.loc[:, column].ffill().bfill()
                column = [(ticker + " " + column) for column in
                          ["Market Volume", "Paid Dividends", "Stock Splits"] for ticker in tickers]
                equity_subset_df.loc[:, column] = equity_subset_df.loc[:, column].fillna(0.0)
                equity_subset_df = equity_subset_df.set_index(equity_subset_df.index.date).sort_index()
                equity_subset_df = equity_subset_df.sort_index(axis=1)
                self.print_log("Data has [{}] columns and [{}] rows post copy".format(len(equity_subset_df.columns), len(equity_subset_df)))
                fx_rates = self.database_read("""
                    from(bucket: "data_public")
                        |> range(start: {}, stop: now())
                        |> filter(fn: (r) => r["_measurement"] == "currency")
                        |> filter(fn: (r) => r["period"] == "1d")
                        |> filter(fn: (r) => r["type"] == "snapshot")
                        |> keep(columns: ["_time", "_value", "_field"])
                        |> group()
                        |> sort(columns: ["_time"])
                                """.format(pytz.UTC.localize(pd.to_datetime(equity_subset_df.index[0])).isoformat()),
                                              ["Date", "Rate", "Pair"], "RBA_FX_rates",
                                              read_cache=library.test(library.WRANGLE_DISABLE_FILE_DOWNLOAD))
                fx_rates = fx_rates.set_index(pd.to_datetime(fx_rates["Date"]).dt.date).sort_index()
                del fx_rates["Date"]
                fx_rates["Rate"] = fx_rates["Rate"].apply(pd.to_numeric)
                index_weights = self.sheet_read(DRIVE_URL_PORTFOLIO, "Index_weights",
                                                read_cache=library.test(library.WRANGLE_DISABLE_FILE_DOWNLOAD),
                                                sheet_params={"sheet": "Indexes", "index": None, "start_row": 2})
                index_weights = index_weights.replace('#N/A', np.nan)
                index_weights = index_weights.set_index(index_weights["Exchange Symbol"]).sort_index()
                index_weights = index_weights[["Holdings Quantity", "Watch Quantity", "Baseline Quantity"]]
                index_weights.columns = index_weights.columns.str.rstrip(' Quantity')
                index_weights[index_weights.columns] = index_weights[index_weights.columns].apply(pd.to_numeric)
                indexes = index_weights.columns.values.tolist()
                self.print_log("Data has [{}] columns and [{}] rows post externals download"
                               .format(len(equity_subset_df.columns), len(equity_subset_df)))
                for ticker in tickers:
                    base_currencies = equity_subset_df[ticker + " Currency Base"]
                    base_currency = base_currencies.loc[~base_currencies.isnull()].values[0]
                    if base_currency == "AUD":
                        equity_subset_df[ticker + " Currency Rate Spot"] = 1.0
                    else:
                        fx_rates_pair = fx_rates[fx_rates["Pair"] == "aud/" + base_currency.lower()]
                        del fx_rates_pair["Pair"]
                        fx_rates_pair.columns = [ticker + " Currency Rate Spot"]
                        equity_subset_df = equity_subset_df.join(fx_rates_pair)
                    for index in index_weights.columns:
                        index_weight = index_weights[index_weights.index == ticker][index]
                        index_weght_value = index_weight.values[0] if len(index_weight) > 0 else 0.0
                        equity_subset_df[ticker + " Index " + index.title() + " Weight"] = index_weght_value
                    for column in [" Price Open", " Price High", " Price Low", " Price Close"]:
                        equity_subset_df[ticker + column + " Base"] = \
                            equity_subset_df[ticker + column] * \
                            equity_subset_df[ticker + " Currency Rate Base"]
                        equity_subset_df[ticker + column + " Spot"] = \
                            equity_subset_df[ticker + column + " Base"] / \
                            equity_subset_df[ticker + " Currency Rate Spot"]
                        for index in indexes:
                            equity_subset_df[ticker + " Index " + index.title() + column + " Base"] = \
                                equity_subset_df[ticker + " Index " + index.title() + " Weight"] * \
                                equity_subset_df[ticker + column + " Base"]
                            equity_subset_df[ticker + " Index " + index.title() + column + " Spot"] = \
                                equity_subset_df[ticker + " Index " + index.title() + " Weight"] * \
                                equity_subset_df[ticker + column + " Spot"]
                self.print_log("Data has [{}] columns and [{}] rows post equity enrichment"
                               .format(len(equity_subset_df.columns), len(equity_subset_df)))
                for index in indexes:
                    equity_subset_df[index + " Currency Base"] = "AUD"
                    equity_subset_df[index + " Paid Dividends"] = 0.0
                    equity_subset_df[index + " Currency Rate Base"] = 1.0
                    equity_subset_df[index + " Currency Rate Spot"] = 1.0
                    equity_subset_df[index + " Stock Splits"] = 0.0
                    equity_subset_df[index + " Market Volume"] = 0.0
                    for column in [" Price Close", " Price High", " Price Low", " Price Open"]:
                        equity_subset_df[index + column] = 0.0
                        for index_ticker_component in tickers:
                            if index_ticker_component not in indexes:
                                equity_subset_df[index + column] += \
                                    equity_subset_df[index_ticker_component + " Index " + index.title() + column + " Spot"]
                        for snapshot in [" Base", " Spot"]:
                            equity_subset_df[index + column + snapshot] = \
                                equity_subset_df[index + column]
                            for index_sub in indexes:
                                equity_subset_df[index + " Index " + index_sub.title() + column + snapshot] = \
                                    equity_subset_df[index + column] if index == index_sub else 0.0
                self.print_log("Data has [{}] columns and [{}] rows post index enrichment"
                               .format(len(equity_subset_df.columns), len(equity_subset_df)))
                for ticker in tickers + indexes:
                    equity_subset_df[ticker + " Market Volume Value"] = \
                        equity_subset_df[ticker + " Market Volume"] * \
                        equity_subset_df[ticker + " Price Close Spot"]
                    for snapshot in ["Base", "Spot"]:
                        for period in [1, 30, 90]:
                            equity_subset_df[ticker + " Price Change " + snapshot + " (" + str(period) + ")"] = \
                                equity_subset_df[ticker + " Price Close " + snapshot].diff(period).fillna(0.0)
                            equity_subset_df[ticker + " Price Change Percentage " + snapshot + " (" + str(period) + ")"] = \
                                equity_subset_df[ticker + " Price Close " + snapshot].pct_change(period).fillna(0.0) * 100
                self.print_log("Data has [{}] columns and [{}] rows post change enrichment"
                               .format(len(equity_subset_df.columns), len(equity_subset_df)))
                equity_subset_df = equity_subset_df.sort_index(axis=1)
                self.print_log("Data has [{}] columns and [{}] rows post enrichment"
                               .format(len(equity_subset_df.columns), len(equity_subset_df)))
                equity_subset_df.index = pd.to_datetime(equity_subset_df.index)
                tickers = [ticker.replace(" Price Close", "") for ticker in equity_subset_df.columns if ticker.endswith("Price Close")]
                for metadata in [
                    ([
                         " Price Close",
                         " Price Close Base",
                         " Price Close Spot",
                         " Market Volume Value",
                         " Index Watch Price Close Base",
                         " Index Watch Price Close Spot",
                         " Index Baseline Price Close Base",
                         " Index Baseline Price Close Spot",
                         " Index Holdings Price Close Base",
                         " Index Holdings Price Close Spot",
                         " Price Change Base (1)",
                         " Price Change Spot (1)",
                     ], "$", "1d"),
                    ([
                         " Price Change Percentage Base (1)",
                         " Price Change Percentage Spot (1)",
                     ], "%", "1d"),
                    ([
                         " Price Change Base (30)",
                         " Price Change Spot (30)",
                     ], "$", "30d"),
                    ([
                         " Price Change Percentage Base (30)",
                         " Price Change Percentage Spot (30)",
                     ], "%", "30d"),
                    ([
                         " Price Change Base (90)",
                         " Price Change Spot (90)",
                     ], "$", "90d"),
                    ([
                         " Price Change Percentage Base (90)",
                         " Price Change Percentage Spot (90)",
                     ], "%", "90d"),
                ]:
                    for column_sub in metadata[0]:
                        columns = []
                        columns_rename = {}
                        for ticker in tickers:
                            columns.append(ticker + column_sub)
                            columns_rename[ticker + column_sub] = ticker.lower()
                        self.database_write(equity_subset_df[columns].rename(columns=columns_rename), global_tags={
                            "type": column_sub.split('(')[0].strip().replace(" ", "-").lower(),
                            "period": metadata[2],
                            "unit": metadata[1]
                        })
                self.print_log("Data has [{}] columns and [{}] rows post serialisation"
                               .format(len(equity_subset_df.columns), len(equity_subset_df)))
                self.state_write()
        except Exception as exception:
            self.print_log("Unexpected error processing equity data", exception)
            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED,
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED) +
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED) -
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED))
        if not len(equity_delta_df):
            self.print_log("No new data found")
        self.counter_write()

    def __init__(self):
        super(Equity, self).__init__("Equity", "1wDj18Imc3q1UWfRDU-h9-Rwb73R6PAm-")
