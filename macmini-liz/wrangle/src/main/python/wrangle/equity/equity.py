from __future__ import print_function

import datetime
import glob
import os
from collections import OrderedDict
from datetime import datetime

import pandas as pd
import pdftotext
from pandas.tseries.offsets import BDay
from pandas.tseries.offsets import BMonthEnd

from .. import library

STATUS_FAILURE = "failure"
STATUS_SKIPPED = "skipped"
STATUS_SUCCESS = "success"

CURRENCIES = ["GBP", "USD", "SGD"]
ATTRIBUTES = ("Date", "Type", "Owner", "Currency", "Rate", "Units", "Value")
PERIODS = {'Monthly': 1, 'Quarterly': 3, 'Yearly': 12, 'Five-Yearly': 5 * 12, 'Decennially': 10 * 12}

STOCK = OrderedDict([
    ('S32.AX', {
        "start": "2016",
        "end of day hour": 15
    }),
    ('WPL.AX', {
        "start": "2009",
        "end of day hour": 15
    }),
    ('SIG.AX', {
        "start": "2006",
        "end of day hour": 15
    }),
    ('OZL.AX', {
        "start": "2009",
        "end of day hour": 15
    }),
    ('VAS.AX', {
        "start": "2010",
        "end of day hour": 15
    }),
    ('VAE.AX', {
        "start": "2016",
        "end of day hour": 15
    }),
    ('VGE.AX', {
        "start": "2014",
        "end of day hour": 15
    }),
    ('VGS.AX', {
        "start": "2015",
        "end of day hour": 15
    }),
])

DRIVE_URL = "https://docs.google.com/spreadsheets/d/1qMllD2sPCPYA-URgyo7cp6aXogJcYNCKQ7Dw35_PCgM"


class Equity(library.Library):

    def _run(self):
        new_data = False
        equity_df = pd.DataFrame()

        for stock in STOCK:
            today = datetime.today()
            stock_start_year = int(STOCK[stock]["start"])
            for year in range(stock_start_year, today.year + 1):
                if year == today.year:
                    for month in range(1 if year == stock_start_year else 1, today.month + 1):
                        new_data = self.stock_download(
                            "{}/Yahoo_{}_{}-{:02}.csv".format(self.input, stock.split('.')[0], year, month),
                            stock,
                            "{}-{:02}-01".format(year, month),
                            "{}-{:02}-{:02}".format(
                                year,
                                month,
                                BDay().rollback(today).day if month == today.month else
                                BMonthEnd().rollforward(datetime.strptime("{}-{:02}-01".format(year, month), '%Y-%m-%d').date()).day),
                            STOCK[stock]["end of day hour"], check=year == today.year and month == today.month)[1] \
                                   or new_data
                else:
                    new_data = self.stock_download(
                        "{}/Yahoo_{}_{}.csv".format(self.input, stock.split('.')[0], year),
                        stock,
                        "{}-{:02}-01".format(year, 1),
                        "{}-{:02}-{:02}".format(
                            year,
                            12,
                            BMonthEnd().rollforward(datetime.strptime("{}-12-31".format(year), '%Y-%m-%d').date()).day),
                        STOCK[stock]["end of day hour"], check=year == today.year and month == today.month)[1] \
                               or new_data

        files = self.drive_sync(self.input_drive, self.input)
        new_data = new_data or all([status[0] for status in files.values()]) and any([status[1] for status in files.values()])

        if new_data:

            for stock in STOCK:
                stock_df = pd.DataFrame()
                stock_ticker = stock.split('.')[0]
                for stock_file_name in glob.glob("{}/Yahoo_{}_*.csv".format(self.input, stock_ticker)):
                    stock_month_df = pd.read_csv(stock_file_name) \
                        .add_prefix("{} ".format(stock_ticker)).rename({"{} Date".format(stock_ticker): 'Date'}, axis=1)
                    stock_month_df["{} FX Rate".format(stock_ticker)] = 1.0
                    stock_df = pd.concat([stock_df, stock_month_df])
                stock_df = stock_df.set_index('Date')
                equity_df = stock_df if len(equity_df) == 0 else \
                    equity_df.merge(stock_df, left_index=True, right_index=True, how='outer')

            statement_data = {}
            for statement_file_name in glob.glob("{}/58861*.pdf".format(self.input)):
                with open(statement_file_name, "rb") as statement_file:
                    statement_date = None
                    statement_type = None
                    statement_owner = None
                    statement_rates = {}
                    statement_data[statement_file_name] = {}
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
                                statement_data[statement_file_name]["Errors"].append("File did not begin with required heading")
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
                            try:
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
                                            for currency in CURRENCIES:
                                                if statement_line.startswith(currency):
                                                    statement_rates[currency] = float(statement_line.split()[4].replace(',', ''))

                                    if statement_type:
                                        for indexes in [
                                            (2, "Situations", CURRENCIES, 5, 10),
                                            (3, "Situations", CURRENCIES, 5, 9),
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
                                                                "Units": float(statement_line.split()[indexes[3]].replace(',', '')),
                                                                "Value": float(statement_line.split()[indexes[4]].replace(',', ''))
                                                            }
                                                            if indexes[1] == "Situations" and line_index < (len(statement_lines) - 1):
                                                                currency = statement_lines[line_index + 1].split()[2]
                                                            statement_position["Ticker"] = \
                                                                'MCK' if statement_owner == 'Jane' and currency == 'USD' else \
                                                                    'MUS' if statement_owner == 'Joint' and currency == 'USD' else \
                                                                        'MUK' if statement_owner == 'Joint' and currency == 'GBP' else \
                                                                            'MSG' if statement_owner == 'Joint' and currency == 'SGD' else \
                                                                                'UNKOWN'
                                                            statement_data[statement_file_name]["Positions"][statement_type + currency] = \
                                                                statement_position
                                                        except Exception:
                                                            None
                            except Exception as exception:
                                statement_data[statement_file_name]['Status'] = STATUS_FAILURE
                                statement_data[statement_file_name]["Errors"].append(
                                    "Statement parse failed with exception [{}: {}]".format(type(exception).__name__, exception))
                            line_index += 1
                        page_index += 1
                if statement_data[statement_file_name]['Status'] == STATUS_SUCCESS:
                    statement_positions = statement_data[statement_file_name]["Positions"]
                    for statement_position in statement_positions.values():
                        if len(statement_positions) == 0 or not all(key in statement_position for key in ATTRIBUTES):
                            statement_data[statement_file_name]['Status'] = STATUS_FAILURE
                            statement_data[statement_file_name]["Errors"] \
                                .append("Statement parse failed to resolve all keys {} in {}".format(ATTRIBUTES, statement_position))

            statements_positions = []
            for file_name in statement_data:
                if statement_data[file_name]['Status'] == STATUS_SUCCESS:
                    statement_position = statement_data[file_name]["Positions"]
                    statements_positions.extend(statement_position.values())
                    self.print_log("File [{}] processed as [{}] with positions {}"
                                   .format(os.path.basename(file_name), STATUS_SUCCESS, statement_position.keys()))
                    self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                elif statement_data[file_name]['Status'] == STATUS_SKIPPED:
                    self.print_log("File [{}] processed as [{}]".format(os.path.basename(file_name), STATUS_SKIPPED))
                    self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED)
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
            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED, len(statement_data)
                             - self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                             - self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED))

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
                ], axis=1)
                columns = []
                tickers = set()
                for column in statement_df.columns:
                    tickers.add(column.split(" ")[0])
                for ticker in sorted(tickers, reverse=True):
                    columns.append("{} Open".format(ticker))
                    columns.append("{} High".format(ticker))
                    columns.append("{} Low".format(ticker))
                    columns.append("{} Close".format(ticker))
                    columns.append("{} Volume".format(ticker))
                    columns.append("{} Dividends".format(ticker))
                    columns.append("{} FX Rate".format(ticker))
                statement_df = statement_df[columns]
                equity_df = statement_df if len(equity_df) == 0 else \
                    equity_df.merge(statement_df, left_index=True, right_index=True, how='outer')

            equity_df = equity_df.resample('D')
            equity_df = equity_df.interpolate().fillna(method='ffill')
            equity_df = equity_df.sort_index(ascending=False)
            equity__delta_df = self.state_cache(equity_df, "Equity")
            if len(equity__delta_df):
                equity_df.insert(0, 'Date', equity_df.index.strftime("%Y-%m-%d").astype(str))
                self.sheet_write(equity_df, DRIVE_URL, {'index': False, 'sheet': 'History', 'start': 'A1', 'replace': True})
                self.state_write()

    def __init__(self, profile_path=".profile"):
        super(Equity, self).__init__("Equity", "1wDj18Imc3q1UWfRDU-h9-Rwb73R6PAm-", profile_path)
