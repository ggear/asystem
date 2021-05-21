from __future__ import print_function

import calendar
import datetime
import os
from collections import OrderedDict
from datetime import datetime

import pandas as pd
import pdftotext

from .. import library

STATUS_FAILURE = "failure"
STATUS_SKIPPED = "skipped"
STATUS_SUCCESS = "success"

STATEMENT_CURRENCIES = ["GBP", "USD", "SGD"]
STATEMENT_ATTRIBUTES = ("Date", "Type", "Owner", "Currency", "Rate", "Units", "Value")

STOCK = OrderedDict([
    ('S32', {
        "start": "2016",
        "end of day": "15:00",
        "exchange": "AX",
    }),
    ('WPL', {
        "start": "2009",
        "end of day": "15:00",
        "exchange": "AX",
    }),
    ('SIG', {
        "start": "2006",
        "end of day": "15:00",
        "exchange": "AX",
    }),
    ('OZL', {
        "start": "2009",
        "end of day": "15:00",
        "exchange": "AX",
    }),
    ('VAS', {
        "start": "2010",
        "end of day": "15:00",
        "exchange": "AX",
    }),
    ('VAE', {
        "start": "2016",
        "end of day": "15:00",
        "exchange": "AX",
    }),
    ('VGE', {
        "start": "2014",
        "end of day": "15:00",
        "exchange": "AX",
    }),
    ('VGS', {
        "start": "2015",
        "end of day": "15:00",
        "exchange": "AX",
    }),
])

DIMENSIONS = [
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
    "Dividends",
    "Stock Splits",
    "FX Rate",
    "Base Currency",
]

DRIVE_URL = "https://docs.google.com/spreadsheets/d/1qMllD2sPCPYA-URgyo7cp6aXogJcYNCKQ7Dw35_PCgM"


class Equity(library.Library):

    def _run(self):
        stock_files = {}
        for stock in STOCK:
            today = datetime.today()
            stock_start_year = int(STOCK[stock]["start"])
            for year in range(stock_start_year, today.year + 1):
                if year == today.year:
                    for month in range(1 if year == stock_start_year else 1, today.month + 1):
                        file_name = "{}/Yahoo_{}_{}-{:02}.csv".format(self.input, stock, year, month)
                        stock_files[file_name] = self.stock_download(
                            file_name,
                            "{}{}{}".format(stock, '.' if STOCK[stock]["exchange"] != "" else '', STOCK[stock]["exchange"]),
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
                        "{}{}{}".format(stock, '.' if STOCK[stock]["exchange"] != "" else '', STOCK[stock]["exchange"]),
                        "{}-{:02}-01".format(year, 1),
                        "{}-{:02}-{:02}".format(
                            year,
                            12,
                            31),
                        STOCK[stock]["end of day"], check=False)
        statement_files = {}
        files = self.drive_sync(self.input_drive, self.input)
        for file_name in files:
            if os.path.basename(file_name).startswith("58861"):
                statement_files[file_name] = files[file_name]
            elif os.path.basename(file_name).startswith("Yahoo"):
                if files[file_name][0] and files[file_name][1]:
                    stock_files[file_name] = files[file_name]
        new_data = (all([status[0] for status in stock_files.values()]) and any([status[1] for status in stock_files.values()])) or \
                   (all([status[0] for status in statement_files.values()]) and any([status[1] for status in statement_files.values()]))
        stocks_df = {}
        for stock_file_name in stock_files:
            if stock_files[stock_file_name][0]:
                if stock_files[stock_file_name][1]:
                    try:
                        stock_ticker = os.path.basename(stock_file_name).split('_')[1]
                        stock_df = pd.read_csv(stock_file_name) \
                            .add_prefix("{} ".format(stock_ticker)).rename({"{} Date".format(stock_ticker): 'Date'}, axis=1)
                        stock_df["{} FX Rate".format(stock_ticker)] = 1.0
                        stock_df["{} Base Currency".format(stock_ticker)] = "AUD"
                        stock_df = stock_df.set_index('Date')
                        if stock_ticker in stocks_df:
                            stocks_df[stock_ticker] = pd.concat([stocks_df[stock_ticker], stock_df], sort=True)
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
                if statement_files[statement_file_name][1]:
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
                                    if len(statement_lines) > 1 and statement_lines[0].startswith("Consolidated Statement"):
                                        statement_data[statement_file_name]['Status'] = STATUS_SUCCESS
                                    elif len(statement_lines) > 1 and "Administration Services" in statement_lines[0]:
                                        statement_data[statement_file_name]['Status'] = STATUS_SKIPPED
                                    else:
                                        statement_data[statement_file_name]["Errors"].append("File missing required heading")
                                while line_index < len(statement_lines):
                                    statement_data[statement_file_name]['Parse'] += "File [{}]: Page [{:02d}]: Line [{:02d}]:  " \
                                        .format(os.path.basename(statement_file_name), page_index, line_index)
                                    statement_line = statement_lines[line_index]
                                    statement_tokens = statement_line.split()
                                    token_index = 0
                                    while token_index < len(statement_tokens):
                                        statement_data[statement_file_name]['Parse'] += u"{:02d}:{} " \
                                            .format(token_index, statement_tokens[token_index])
                                        token_index += 1
                                    statement_data[statement_file_name]['Parse'] += "\n"
                                    if statement_data[statement_file_name]['Status'] == STATUS_SUCCESS:
                                        if page_index == 0:
                                            if statement_line.startswith("Account name"):
                                                if "Jane" in statement_line and "Graham" in statement_line:
                                                    statement_type = "Fund "
                                                    statement_owner = "Joint"
                                                elif "Jane" in statement_line and not "Graham" in statement_line:
                                                    statement_type = "Equity "
                                                    statement_owner = "Jane"
                                                else:
                                                    statement_data[statement_file_name]['Status'] = STATUS_FAILURE
                                                    statement_data[statement_file_name]["Errors"] \
                                                        .append("Could not determine statement type or owner from line [{}]"
                                                                .format(statement_line))
                                            if statement_line.startswith("Statement date"):
                                                statement_date = datetime.strptime(statement_line.split()[2], '%d-%b-%y')
                                            if statement_type:
                                                for currency in STATEMENT_CURRENCIES:
                                                    if statement_line.startswith(currency):
                                                        statement_rates[currency] = \
                                                            float(statement_line.split()[4].replace(',', ''))
                                        if statement_type:
                                            for indexes in [
                                                (2, "Situations", STATEMENT_CURRENCIES, 5, 10),
                                                (3, "Situations", STATEMENT_CURRENCIES, 5, 9),
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
                                                                    "Units": float(statement_line.split()
                                                                                   [indexes[3]].replace(',', '')),
                                                                    "Value": float(statement_line.split()
                                                                                   [indexes[4]].replace(',', ''))
                                                                }
                                                                if indexes[1] == "Situations" and \
                                                                        line_index < (len(statement_lines) - 1):
                                                                    currency = statement_lines[line_index + 1].split()[2]
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
                                                            except Exception:
                                                                None
                                    line_index += 1
                                page_index += 1
                        except Exception as exception:
                            statement_data[statement_file_name]['Status'] = STATUS_FAILURE
                            statement_data[statement_file_name]["Errors"].append(
                                "Statement parse failed with exception [{}: {}]"
                                    .format(type(exception).__name__, exception))
                    if statement_data[statement_file_name]['Status'] == STATUS_SUCCESS:
                        statement_positions = statement_data[statement_file_name]["Positions"]
                        for statement_position in statement_positions.values():
                            if len(statement_positions) == 0 or not all(key in statement_position for key in STATEMENT_ATTRIBUTES):
                                statement_data[statement_file_name]['Status'] = STATUS_FAILURE
                                statement_data[statement_file_name]["Errors"] \
                                    .append("Statement parse failed to resolve all keys {} in {}"
                                            .format(STATEMENT_ATTRIBUTES, statement_position))
        if new_data:
            try:
                statements_positions = []
                counter_files_processed = self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                for file_name in statement_data:
                    if statement_data[file_name]['Status'] == STATUS_SUCCESS:
                        statement_position = statement_data[file_name]["Positions"]
                        statements_positions.extend(statement_position.values())
                        self.print_log("File [{}] processed as [{}] with positions {}"
                                       .format(os.path.basename(file_name), STATUS_SUCCESS, statement_position.keys()))
                        self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                    elif statement_data[file_name]['Status'] == STATUS_SKIPPED:
                        self.print_log("File [{}] processed as [{}]".format(os.path.basename(file_name), STATUS_SKIPPED))
                        self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                    else:
                        self.print_log("File [{}] processed as [{}] at parsing point:"
                                       .format(os.path.basename(file_name), STATUS_FAILURE))
                        self.print_log(statement_data[file_name]["Parse"].split("\n"))
                        self.print_log("File [{}] processed as [{}] with errors:".format(os.path.basename(file_name), STATUS_FAILURE))
                        if not statement_data[file_name]["Errors"]:
                            statement_data[file_name]["Errors"] = ["<NONE>"]
                        error_index = 0;
                        while error_index < len(statement_data[file_name]["Errors"]):
                            self.print_log(" {:2d}: {}".format(error_index, statement_data[file_name]["Errors"][error_index]))
                            error_index += 1
                counter_files_skipped = sum([not status[1] for status in statement_files.values()])
                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED, counter_files_skipped)
                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED, len(statement_files) -
                                 (self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                                  - counter_files_processed + counter_files_skipped))
                statement_df = pd.DataFrame(statements_positions)
                if len(statement_df) > 0:
                    statement_df["Price"] = statement_df["Value"] / statement_df["Units"]
                    statement_df['Rate'] = 1.0 / statement_df['Rate']
                    statement_df['Zero'] = 0
                    statement_df = statement_df.set_index('Date')
                    statement_df = pd.concat([
                        statement_df.pivot(columns='Ticker', values='Price').add_suffix(' Open'),
                        statement_df.pivot(columns='Ticker', values='Price').add_suffix(' High'),
                        statement_df.pivot(columns='Ticker', values='Price').add_suffix(' Low'),
                        statement_df.pivot(columns='Ticker', values='Price').add_suffix(' Close'),
                        statement_df.pivot(columns='Ticker', values='Zero').add_suffix(' Volume'),
                        statement_df.pivot(columns='Ticker', values='Zero').add_suffix(' Dividends'),
                        statement_df.pivot(columns='Ticker', values='Zero').add_suffix(' Stock Splits'),
                        statement_df.pivot(columns='Ticker', values='Rate').add_suffix(' FX Rate'),
                        statement_df.pivot(columns='Ticker', values='Currency').add_suffix(' Base Currency'),
                    ], axis=1)
                    statement_df.index = pd.to_datetime(statement_df.index)
                    statement_df = statement_df.resample('D')
                    statement_df = statement_df.interpolate()
                    for column in statement_df.columns:
                        if column.endswith('Base Currency'):
                            last = statement_df[column].last_valid_index()
                            statement_df[column].loc[:last] = statement_df[column].loc[:last].ffill()
                equity_df = pd.DataFrame()
                for stock in STOCK:
                    if stock in stocks_df:
                        equity_df = pd.concat([equity_df, stocks_df[stock]], axis=1, sort=True)
                equity_df.index = pd.to_datetime(equity_df.index)
                equity_df = equity_df.resample('D')
                equity_df = equity_df.fillna(method='backfill')
                equity_df = pd.concat([equity_df, statement_df], axis=1, sort=True)
                equity_df.index = pd.to_datetime(equity_df.index)
                equity_df = equity_df[~equity_df.index.duplicated(keep='last')]
                equity_df.index = pd.to_datetime(equity_df.index)
                columns = []
                tickers = set()
                for column in equity_df.columns:
                    ticker = column.split(" ")[0]
                    if ticker not in tickers:
                        tickers.add(ticker)
                        for dimension in DIMENSIONS:
                            columns.append("{} {}".format(ticker, dimension))
                equity_df = equity_df[columns]
                equity_delta_df, equity_current_df, _ = self.state_cache(equity_df, "Equity")
                if len(equity_delta_df):
                    equity_current_df.index = equity_current_df.index.strftime('%Y-%m-%d')
                    self.sheet_write(equity_current_df.sort_index(ascending=False), DRIVE_URL,
                                     {'index': True, 'sheet': 'History', 'start': 'A1', 'replace': True})

                    # TODO: Provide a database_write implementation

                    self.state_write()
                else:
                    new_data = False
            except Exception as exception:
                self.print_log("Unexpected error processing equity data", exception)
                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED,
                                 self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED) +
                                 self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED) -
                                 self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED))
        else:
            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED, len(statement_files))
        if not new_data:
            self.print_log("No new data found")

    def __init__(self):
        super(Equity, self).__init__("Equity", "1wDj18Imc3q1UWfRDU-h9-Rwb73R6PAm-")
