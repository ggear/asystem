import calendar
import datetime
import time
from collections import OrderedDict
from datetime import datetime
from os.path import *

import pdftotext
import polars as pl
import polars.selectors as cs
import pytz

from .. import library
from ..library import PL_PRINT_ROWS

STATUS_FAILURE = "failure"
STATUS_SKIPPED = "skipped"
STATUS_SUCCESS = "success"

CURRENCIES = ["GBP", "USD", "SGD"]

DIMENSIONS_CHANGE_PERIODS = [
    1, 30, 90, 365
]
DIMENSIONS_PRICE_TYPES = [
    "Base",
    "Spot",
]
DIMENSIONS_PRICE = [
    "Price Open",
    "Price High",
    "Price Low",
    "Price Close",
]
DIMENSIONS_CHANGE = [
    "Price Close {}{}d-Change {}".format(price_type, change_period, change_type).strip()
    for price_type in [""] + ["{} ".format(dimension) for dimension in DIMENSIONS_PRICE_TYPES]
    for change_period in DIMENSIONS_CHANGE_PERIODS
    for change_type in ["Absolute", "Percentage"]
]
DIMENSIONS_VOLUME = [
    "Market Volume Spot",
]
DIMENSIONS_AUX = [
    "Market Volume",
    "Paid Dividends",
    "Stock Splits",
    "Currency Base",
    "Currency Rate Base",
]
DIMENSIONS_AUX_TYPES = [
    "Currency Rate Spot",
]
DIMENSIONS_PRICE_AUX = DIMENSIONS_PRICE + DIMENSIONS_AUX
DIMENSIONS_PRICE_AUX_TYPES = (
        ["{} {}".format(price, price_type).strip()
         for price in DIMENSIONS_PRICE for price_type in [""] + DIMENSIONS_PRICE_TYPES]
        + DIMENSIONS_AUX + DIMENSIONS_AUX_TYPES
)
DIMENSIONS_ALL = (
        ["{} {}".format(price, price_type).strip()
         for price in DIMENSIONS_PRICE if price != "Price Close" for price_type in [""] + DIMENSIONS_PRICE_TYPES]
        + sorted(["Price Close", "Price Close Base", "Price Close Spot"] + DIMENSIONS_CHANGE)
        + DIMENSIONS_VOLUME + DIMENSIONS_AUX + DIMENSIONS_AUX_TYPES
)

STATEMENT_ATTRIBUTES = ("Date", "Type", "Owner", "Currency", "Rate", "Units", "Value")

STOCK = OrderedDict([
    ('AORD', {"start": "1985-01", "end of day": "16:00", "prefix": "^", "exchange": "", }),
    ('SIG', {"start": "2006-01", "end of day": "16:00", "prefix": "", "exchange": "AX", }),
    ('WDS', {"start": "2009-01", "end of day": "16:00", "prefix": "", "exchange": "AX", }),
    ('GOLD', {"start": "2008-01", "end of day": "16:00", "prefix": "", "exchange": "AX", }),
    ('VAS', {"start": "2010-01", "end of day": "16:00", "prefix": "", "exchange": "AX", }),
    ('VHY', {"start": "2011-01", "end of day": "16:00", "prefix": "", "exchange": "AX", }),
    ('VGS', {"start": "2014-12", "end of day": "16:00", "prefix": "", "exchange": "AX", }),
    ('VGE', {"start": "2014-01", "end of day": "16:00", "prefix": "", "exchange": "AX", }),
    ('VAE', {"start": "2016-01", "end of day": "16:00", "prefix": "", "exchange": "AX", }),
    ('VDHG', {"start": "2018-01", "end of day": "16:00", "prefix": "", "exchange": "AX", }),
    ('IAF', {"start": "2012-04", "end of day": "16:00", "prefix": "", "exchange": "AX", }),
    ('ACDC', {"start": "2018-09", "end of day": "16:00", "prefix": "", "exchange": "AX", }),
    ('CLNE', {"start": "2021-04", "end of day": "16:00", "prefix": "", "exchange": "AX", }),
    ('ERTH', {"start": "2021-04", "end of day": "16:00", "prefix": "", "exchange": "AX", }),
    ('URNM', {"start": "2022-07", "end of day": "16:00", "prefix": "", "exchange": "AX", }),
])

DRIVE_KEY_PRICES = "1qMllD2sPCPYA-URgyo7cp6aXogJcYNCKQ7Dw35_PCgM"
DRIVE_KEY_PORTFOLIO = "1Kf9-Gk7aD4aBdq2JCfz5zVUMWAtvJo2ZfqmSQyo8Bjk"


class Equity(library.Library):

    # noinspection PyTypeChecker,PyUnresolvedReferences
    def _run(self):
        new_data = False
        started_time = time.time()
        equity_df = self.dataframe_new(schema={"Date": pl.Date}, print_rows=-1)
        equity_delta_df = self.dataframe_new(schema={"Date": pl.Date}, print_rows=-1)
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
            files = self.drive_synchronise(self.input_drive, self.input, download=(not library.test(library.WRANGLE_DISABLE_FILE_DOWNLOAD)))
            self.add_counter(library.CTR_SRC_SOURCES, library.CTR_ACT_CACHED, -1 * (files_cached + files_downloaded))
            for file_name in files:
                if basename(file_name).startswith("58861"):
                    statement_files[file_name] = files[file_name]
                elif basename(file_name).startswith("Yahoo"):
                    if files[file_name][0] and (library.test(library.WRANGLE_DISABLE_DATA_DELTA) or files[file_name][1]):
                        stock_files[file_name] = files[file_name]
            new_data = library.test(library.WRANGLE_DISABLE_DATA_DELTA) or \
                       (all([status[0] for status in list(stock_files.values())]) and any(
                           [status[1] for status in list(stock_files.values())])) or \
                       (all([status[0] for status in list(statement_files.values())]) and any(
                           [status[1] for status in list(statement_files.values())]))
        if library.test(library.WRANGLE_DISABLE_DATA_DELTA):
            stock_files = self.file_list(self.input, "Yahoo")
            statement_files = self.file_list(self.input, "58861")
            new_data = len(stock_files) > 0 or len(statement_files) > 0
        self.print_log("Files [Equity] downloaded or cached [{}] stock and [{}] fund files"
                       .format(len(stock_files), len(statement_files)), started=started_time)
        started_time = time.time()
        stocks_df = {}
        stocks_files_count = 0
        for stock_file_name in stock_files:
            if stock_files[stock_file_name][0]:
                if library.test(library.WRANGLE_DISABLE_DATA_DELTA) or stock_files[stock_file_name][1]:
                    try:
                        stocks_files_count += 1
                        stock_ticker = basename(stock_file_name).split('_')[1]
                        stock_df = self.csv_read(stock_file_name, schema={
                            "Date": pl.Date,
                            "Open": pl.Float64,
                            "High": pl.Float64,
                            "Low": pl.Float64,
                            "Close": pl.Float64,
                            "Volume": pl.Int64,
                            "Dividends": pl.Float64,
                            "Stock Splits": pl.Float64,
                        })
                        stock_df = stock_df.with_columns([pl.lit("AUD").alias("Base"), pl.lit(1.0).alias("Rate")])
                        stock_df.columns = ["Date"] + ["{} {}".format(stock_ticker, column) for column in DIMENSIONS_PRICE_AUX]
                        if stock_ticker in stocks_df:
                            stocks_df[stock_ticker] = pl.concat([stocks_df[stock_ticker], stock_df])
                        else:
                            stocks_df[stock_ticker] = stock_df
                        self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
                    except Exception as exception:
                        self.print_log("Unexpected error processing file [{}]".format(stock_file_name), exception=exception)
                        self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
                else:
                    self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED)
            else:
                self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED)
        for stock_ticker in stocks_df:
            self.dataframe_print(stocks_df[stock_ticker], print_label=stock_ticker, print_verb="collected")
        self.print_log("DataFrame [Stocks] collected with [{}] stocks across [{}] files"
                       .format(len(stocks_df), stocks_files_count), started=started_time)
        started_time = time.time()
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
                            statement_pages = pdftotext.PDF(statement_file, physical=True)
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
                                        .format(basename(statement_file_name), page_index, line_index)
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
                                                for currency in CURRENCIES:
                                                    if statement_line.startswith(currency):
                                                        statement_rates[currency] = \
                                                            float(statement_tokens[4].replace(',', ''))
                                        if statement_type:
                                            for indexes in [
                                                (2, "Situations", CURRENCIES, 5, 10, 2, 6),
                                                (2, "Situations", CURRENCIES, 8, 13, 2, 6),
                                                (3, "Situations", CURRENCIES, 5, 9, 2, 6),
                                                (2, "Shares", ["USD"], 2, 7),
                                                (3, "Shares", ["USD"], 2, 6),
                                            ]:
                                                if page_index == indexes[0] and indexes[1] in statement_line:
                                                    for currency in indexes[2]:
                                                        if indexes[1] == "Shares" or currency in statement_line:
                                                            try:
                                                                statement_position = {
                                                                    "Date": statement_date.strftime('%Y-%m-%d'),
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
        self.print_log("File [Funds] parsed [{}] statements".format(len(statement_data)), started=started_time)

        def _equity_tickers(_equity_df):
            return sorted([column.replace(" Price Close", "") \
                           for column in _equity_df.columns if column.endswith("Price Close")])

        def _equity_columns(_equity_df, _ticker):
            return [_column for _column in _equity_df.columns if _column.startswith(_ticker)]

        def _equity_clean(_equity_df):
            for _ticker in _equity_tickers(_equity_df):
                _equity_df = _equity_df.with_columns(
                    pl.when(pl.col("{} Price Close".format(_ticker)).is_null()).then(None) \
                        .otherwise(pl.col(_equity_columns(_equity_df, _ticker))).name.keep())
            _equity_df = _equity_df.filter(~pl.all_horizontal(pl.all().exclude("Date").is_null())) \
                .sort("Date").set_sorted("Date")
            return _equity_df

        def _equity_upsample(_equity_df):
            return _equity_df \
                .unique(subset=["Date"], keep="first").sort("Date").set_sorted("Date") \
                .upsample(time_column="Date", every="1d").fill_nan(pl.lit(None)) \
                .with_columns(cs.numeric().interpolate()) \
                .with_columns(cs.string().forward_fill())

        def _equity_print(_equity_df, _dimensions=DIMENSIONS_PRICE_AUX,
                          print_label=None, print_verb=None, print_rows=PL_PRINT_ROWS, started=None):
            self.dataframe_print(_equity_df, print_label=print_label, print_verb=print_verb,
                                 print_suffix="(data to follow)", print_rows=0, started=started)
            if len(_equity_df) > 0:
                for _ticker in _equity_tickers(_equity_df):
                    _ticker_df = _equity_df.select(["Date"] + \
                                                   ["{} {}".format(_ticker, _dimension) for _dimension in _dimensions]) \
                        .fill_nan(None).filter(~pl.all_horizontal(pl.all().exclude("Date").is_null()))
                    self.dataframe_print(_ticker_df, print_label="{}_{}".format(print_label, _ticker),
                                         print_verb=print_verb, print_rows=print_rows)

        try:
            if new_data:
                started_time = time.time()
                statements_positions = []
                for file_name in statement_data:
                    if statement_data[file_name]['Status'] == STATUS_SUCCESS:
                        statement_position = statement_data[file_name]["Positions"]
                        statements_positions.extend(list(statement_position.values()))
                        self.print_log("File [{}] processed as [{}] with positions {}"
                                       .format(basename(file_name), STATUS_SUCCESS, list(statement_position.keys())))
                    elif statement_data[file_name]['Status'] == STATUS_SKIPPED:
                        self.print_log("File [{}] processed as [{}]".format(basename(file_name), STATUS_SKIPPED))
                    else:
                        self.print_log("File [{}] processed as [{}] at parsing point:".format(basename(file_name), STATUS_FAILURE))
                        self.print_log(statement_data[file_name]["Parse"].split("\n"))
                        self.print_log("File [{}] processed as [{}] with errors:".format(basename(file_name), STATUS_FAILURE))
                        if not statement_data[file_name]["Errors"]:
                            statement_data[file_name]["Errors"] = ["<NONE>"]
                        error_index = 0
                        while error_index < len(statement_data[file_name]["Errors"]):
                            self.print_log(" {:2d}: {}".format(error_index, statement_data[file_name]["Errors"][error_index]))
                            error_index += 1
                if len(statements_positions) == 0:
                    statement_df = self.dataframe_new(schema={"Date": pl.Date}, print_label="Funds", started=started_time)
                else:
                    statement_df = self.dataframe_new(statements_positions, print_label="Funds", started=started_time)
                    started_time = time.time()
                    tickers = [row[0] for row in statement_df.select("Ticker").unique().rows()]
                    statement_df = statement_df.with_columns(
                        pl.col("Date").str.strptime(pl.Date),
                        (pl.col("Value") / pl.col("Units")).alias("Price"),
                        (1.0 / pl.col("Rate")).alias("Rate"),
                    ).pivot(values=["Price", "Rate", "Currency"], index="Date", columns="Ticker").sort("Date")
                    self.dataframe_print(statement_df, print_label="Funds", print_verb="pivoted", started=started_time)
                    started_time = time.time()
                    columns = []
                    for statement_column in statement_df.columns:
                        if statement_column.startswith("Price_Ticker_"):
                            columns.append("{} Price Close".format(statement_column.replace("Price_Ticker_", "")))
                        elif statement_column.startswith("Rate_Ticker_"):
                            columns.append("{} Currency Rate Base".format(statement_column.replace("Rate_Ticker_", "")))
                        elif statement_column.startswith("Currency_Ticker_"):
                            columns.append("{} Currency Base".format(statement_column.replace("Currency_Ticker_", "")))
                        else:
                            columns.append(statement_column)
                    statement_df.columns = columns
                    self.dataframe_print(statement_df, print_label="Funds", print_verb="renamed", started=started_time)
                    started_time = time.time()
                    for ticker in tickers:
                        statement_df = statement_df.with_columns([
                            pl.col("{} Price Close".format(ticker)).alias("{} Price Open".format(ticker)),
                            pl.col("{} Price Close".format(ticker)).alias("{} Price High".format(ticker)),
                            pl.col("{} Price Close".format(ticker)).alias("{} Price Low".format(ticker)),
                            pl.lit(0.0, pl.Int64).alias("{} Market Volume".format(ticker)),
                            pl.lit(0.0, pl.Float64).alias("{} Paid Dividends".format(ticker)),
                            pl.lit(0.0, pl.Float64).alias("{} Stock Splits".format(ticker)),
                        ])
                    statement_df = statement_df.select(["Date"] + ["{} {}".format(ticker, dimension)
                                                                   for ticker in tickers for dimension in DIMENSIONS_PRICE_AUX])
                    statement_df = _equity_upsample(statement_df)
                    statement_df = _equity_clean(statement_df)
                _equity_print(statement_df, print_label="Funds", print_verb="enriched", started=started_time)
                started_time = time.time()
                for stock in STOCK:
                    if stock in stocks_df:
                        equity_df = equity_df.join(stocks_df[stock], on="Date", how="outer")
                equity_df = _equity_upsample(equity_df)
                _equity_print(equity_df, print_label="Stocks", print_verb="concatenated", started=started_time)
                started_time = time.time()

                # TODO: Add BSAV
                # bank_name = "RBA_Interest_Bank_rates"
                # bank_cols = OrderedDict([("Date", "object"), ("Bank Rate", "float64")])
                # bank_query = """
                # from(bucket: "data_public")
                #     |> range(start: 1993-01-01T00:00:00.000Z, stop: now())
                #     |> filter(fn: (r) => r["_measurement"] == "interest")
                #     |> filter(fn: (r) => r["_field"] == "bank")
                #     |> filter(fn: (r) => r["period"] == "1mo")
                #     |> keep(columns: ["_time", "_value"])
                #     |> sort(columns: ["_time"])
                #     |> sort(columns: ["_time"])
                #     |> unique(column: "_time")
                #                 """
                # bank_rates = self.database_read(bank_name, bank_query, bank_cols, library.test(library.WRANGLE_DISABLE_FILE_DOWNLOAD),
                #       engine=PANDAS_ENGINE, dtype_backend=PANDAS_BACKEND)
                # if not library.test(library.WRANGLE_DISABLE_FILE_DOWNLOAD) and len(bank_rates) == 0:
                #     bank_rates = self.database_read(bank_name, bank_query, bank_cols, True,
                #       engine=PANDAS_ENGINE, dtype_backend=PANDAS_BACKEND)
                # bank_rates.loc[len(bank_rates.index)] = \
                #     [datetime.today().strftime('%Y-%m-%d 00:00:00+00:00'), bank_rates.loc[len(bank_rates.index) - 1, "Bank Rate"]]
                # bank_rates["Bank Rate"] = bank_rates["Bank Rate"].apply(pd.to_numeric)
                # bank_rates["BSAV Price Open"] = 1
                # bank_rates["BSAV Price Close"] = bank_rates["Bank Rate"] / 1200 + 1
                # for i in range(1, len(bank_rates)):
                #     bank_rates.loc[i, "BSAV Price Open"] = bank_rates.loc[i - 1, "BSAV Price Close"]
                #     bank_rates.loc[i, "BSAV Price Close"] = bank_rates.loc[i, "BSAV Price Open"] * \
                #                                             (bank_rates.loc[i, "Bank Rate"] / 1200 + 1)
                # bank_rates.index = pd.to_datetime(pd.to_datetime(bank_rates["Date"], utc=True).dt.date)
                # bank_rates.sort_index(inplace=True)
                # bank_rates = bank_rates[~bank_rates.index.duplicated(keep='last')]
                # bank_rates = bank_rates.resample('D').interpolate(limit_direction='both', limit_area='inside').replace('', np.nan).ffill()
                # bank_rates["BSAV Price Close"] = bank_rates["BSAV Price Open"]
                # bank_rates["BSAV Price Low"] = bank_rates[["BSAV Price Open", "BSAV Price Close"]].min(axis=1)
                # bank_rates["BSAV Price High"] = bank_rates[["BSAV Price Open", "BSAV Price Close"]].max(axis=1)
                # bank_rates["BSAV Currency Base"] = "AUD"
                # bank_rates["BSAV Paid Dividends"] = 0.0
                # bank_rates["BSAV Currency Rate Base"] = 1.0
                # bank_rates["BSAV Currency Rate Spot"] = 1.0
                # bank_rates["BSAV Stock Splits"] = 0.0
                # bank_rates["BSAV Market Volume"] = 0.0
                # del bank_rates["Date"]
                # del bank_rates["Bank Rate"]
                # equity_df = pd.concat([equity_df, bank_rates], axis=1, sort=True)

                equity_df = equity_df.join(statement_df, on="Date", how="outer")
                equity_df = equity_df.unique(subset=["Date"], keep="first").sort("Date").set_sorted("Date")
                _equity_print(equity_df, print_label="Equity", print_verb="concatenated", started=started_time)
                started_time = time.time()
                equity_df_manual = self.sheet_download("Manual_Stock_Prices_Sheet", DRIVE_KEY_PRICES, sheet_name="Manual",
                                                       schema={"Date": pl.Date}, write_cache=library.test(library.WRANGLE_ENABLE_DATA_CACHE))
                equity_df_manual = _equity_upsample(equity_df_manual)
                tickers_manual = _equity_tickers(equity_df_manual)
                for ticker in tickers_manual:
                    equity_df_manual = equity_df_manual.with_columns([
                        pl.col("{} Price Close".format(ticker)).alias("{} Price Open".format(ticker)),
                        pl.col("{} Price Close".format(ticker)).alias("{} Price High".format(ticker)),
                        pl.col("{} Price Close".format(ticker)).alias("{} Price Low".format(ticker)),
                        pl.lit(0.0).alias("{} Market Volume".format(ticker)),
                        pl.lit(0.0).alias("{} Paid Dividends".format(ticker)),
                        pl.lit(0.0).alias("{} Stock Splits".format(ticker)),
                        pl.lit("AUD").alias("{} Currency Base".format(ticker)),
                    ])
                equity_df_manual = _equity_clean(equity_df_manual)
                _equity_print(equity_df_manual, print_label="Equity_Manual_Stock_Prices", print_verb="processed", started=started_time)
                started_time = time.time()
                tickers = _equity_tickers(equity_df)
                for ticker in tickers_manual:
                    if ticker in tickers:
                        equity_df = equity_df.update(equity_df_manual, on="Date", how="outer")
                    else:
                        equity_df = pl.concat([equity_df, equity_df_manual], how="align")
                equity_df = _equity_upsample(equity_df)
                tickers = _equity_tickers(equity_df)
                equity_df = equity_df.select(
                    ["Date"] + ["{} {}".format(ticker, dimension) for ticker in tickers for dimension in DIMENSIONS_PRICE_AUX])
                equity_df = _equity_clean(equity_df)
                _equity_print(equity_df, print_label="Equity", print_verb="added manual stock prices", started=started_time)
                started_time = time.time()
                columns = []
                for ticker in tickers:
                    for dimension_diff in DIMENSIONS_PRICE_AUX:
                        column = "{} {}".format(ticker, dimension_diff)
                        columns.append(column)
                        if column not in equity_df:
                            if dimension_diff.contains("Price"):
                                equity_df = equity_df.with_columns(pl.col("{} Price Close".format(ticker)).alias(column))
                            elif dimension_diff in ["Market Volume"]:
                                equity_df = equity_df.with_columns(pl.lit(0.0).alias(column).cast(pl.Int64))
                            elif dimension_diff in ["Paid Dividends", "Stock Splits"]:
                                equity_df = equity_df.with_columns(pl.lit(0.0).alias(column).cast(pl.Float64))
                            elif dimension_diff == "Currency Rate Base":
                                equity_df = equity_df.with_columns(pl.lit(1.0).alias(column).cast(pl.Float64))
                            elif dimension_diff == "Currency Base":
                                equity_df = equity_df.with_columns(pl.lit("AUD").alias(column).cast(pl.Utf8))
                equity_df = equity_df.select(["Date"] + columns).sort("Date")
                _equity_print(equity_df, print_label="Equity", print_verb="sorted", started=started_time)
        except Exception as exception:
            self.print_log("Unexpected error processing equity dataframe", exception=exception)
            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED,
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED) +
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED) -
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED))
        try:
            def _aggregate_function(_data_df):
                _columns = []
                for _ticker in _equity_tickers(_data_df):
                    for _dimension in DIMENSIONS_PRICE_AUX:
                        _column = "{} {}".format(_ticker, _dimension)
                        _columns.append(_column)
                        if _dimension == "Currency Base":
                            _data_df = _data_df.with_columns(pl.col(_column).cast(pl.Utf8))
                        else:
                            _data_df = _data_df.with_columns(pl.col(_column).cast(pl.Float64))
                return _data_df.select(["Date"] + _columns).with_columns(cs.float().round(4))

            equity_delta_df, equity_current_df, _ = self.state_cache(_aggregate_function(equity_df), _aggregate_function)
            if len(equity_delta_df):




                # TODO: Update for delta
                started_time = time.time()
                dimensions_sheet = ["Price Close", "Currency Rate Base"]
                tickers = _equity_tickers(equity_current_df)
                equity_sheet_df = equity_current_df.select(
                    ["Date"] + ["{} {}".format(ticker, dimension) for ticker in tickers for dimension in dimensions_sheet])
                equity_sheet_df = equity_sheet_df \
                    .filter(pl.col("Date") > pl.lit(datetime(2007, 1, 1))).sort("Date", descending=True)
                _equity_print(equity_sheet_df, _dimensions=dimensions_sheet,
                              print_label="Sheet", print_verb="filtered", started=started_time)
                self.sheet_upload(equity_sheet_df, DRIVE_KEY_PRICES, sheet_name='History')







                # TODO: Move to pre-state
                started_time = time.time()
                equity_database_df = equity_current_df.clone()
                equity_database_df = _equity_clean(equity_database_df)
                _equity_print(equity_database_df, print_label="Database", print_verb="validated", started=started_time)
                started_time = time.time()
                fx_rates = {}
                started_fx = pytz.UTC.localize(datetime.combine(equity_database_df.head(1).rows()[0][0],
                                                                datetime.min.time())).isoformat()
                for fx_pair in CURRENCIES:
                    fx_file = abspath("{}/_RBA_{}_Rates_Database_Query.csv".format(self.input, fx_pair))
                    fx_query = """
from(bucket: "data_public")
    |> range(start: {}, stop: now())
    |> filter(fn: (r) => r["_measurement"] == "currency")
    |> filter(fn: (r) => r["period"] == "1d")
    |> filter(fn: (r) => r["type"] == "snapshot")
    |> filter(fn: (r) => r["_field"] == "aud/{}")
    |> keep(columns: ["_time", "_value"])
    |> sort(columns: ["_time"])
    |> unique(column: "_time")
    |> rename(columns: {{_time: "Date", _value: "Rate"}})
                    """.format(started_fx, fx_pair.lower())
                    fx_rates[fx_pair] = self.database_download(fx_file, fx_query, schema={"Date": pl.Date},
                                                               check=library.test(library.WRANGLE_DISABLE_FILE_DOWNLOAD),
                                                               force=library.test(library.WRANGLE_ENABLE_DATA_CACHE))
                    fx_rates[fx_pair] = _equity_upsample(fx_rates[fx_pair])
                for ticker in tickers:
                    base_currency = equity_database_df.select("{} Currency Base".format(ticker)).drop_nulls().head(1).rows()[0][0]
                    if base_currency == "AUD":
                        equity_database_df = equity_database_df.with_columns(
                            pl.when(pl.col("{} Price Close".format(ticker)).is_null()).then(None) \
                                .otherwise(pl.lit(1.0)).alias("{} Currency Rate Spot".format(ticker)))
                    else:
                        equity_database_df = equity_database_df.join(fx_rates[base_currency], on="Date", how="outer") \
                            .with_columns(pl.col("Rate").alias("{} Currency Rate Spot".format(ticker))).drop("Rate")
                    for column_price in DIMENSIONS_PRICE:
                        for column_price_type in DIMENSIONS_PRICE_TYPES:
                            equity_database_df = equity_database_df.with_columns( \
                                (pl.col("{} {}".format(ticker, column_price)) *
                                 pl.col("{} Currency Rate {}".format(ticker, column_price_type))) \
                                    .alias("{} {} {}".format(ticker, column_price, column_price_type)))
                equity_database_df = equity_database_df \
                    .select(["Date"] + ["{} {}".format(ticker, column) \
                                        for ticker in sorted(tickers) for column in DIMENSIONS_PRICE_AUX_TYPES])
                for ticker in tickers:
                    equity_database_df = equity_database_df.with_columns(
                        pl.when(pl.col("{} Price Close".format(ticker)).is_null()).then(None) \
                            .otherwise(pl.col("{} Currency Rate Spot".format(ticker))).name.keep())
                _equity_print(equity_database_df, _dimensions=DIMENSIONS_PRICE_AUX_TYPES,
                              print_label="Equity", print_verb="added FX rates", started=started_time)






                # TODO: Move to pre-state
                index_weights = self.sheet_download("Index_Weights_Sheet", DRIVE_KEY_PORTFOLIO, sheet_name="Indexes",
                                                    sheet_start_row=2, write_cache=library.test(library.WRANGLE_ENABLE_DATA_CACHE))
                started_time = time.time()
                indexes = sorted([column.rstrip(" Quantity") for column in index_weights.columns if column.endswith("Quantity")])
                index_weights = index_weights \
                    .select(["Exchange Symbol"] + ["{} Quantity".format(index) for index in indexes]).drop_nulls()
                index_weights.columns = ["Ticker"] + indexes
                index_weights = index_weights.unique(subset=["Ticker"], keep="first").sort("Ticker").set_sorted("Ticker")
                self.dataframe_print(index_weights, print_label="Index_Weights_Sheet",
                                     print_verb="processed", print_rows=1000, started=started_time)
                started_time = time.time()
                for ticker in tickers:
                    for index in indexes:
                        weight_rows = index_weights.filter((pl.col("Ticker") == ticker)).select([index]).head(1).rows()
                        equity_database_df = equity_database_df.with_columns( \
                            pl.lit(weight_rows[0][0] if len(weight_rows) > 0 else 0.0) \
                                .alias("{} Index {} Weight".format(ticker, index.title())))
                    for index in indexes:
                        for column_price in DIMENSIONS_PRICE:
                            equity_database_df = equity_database_df.with_columns( \
                                (pl.col("{} {} Spot".format(ticker, column_price)) *
                                 pl.col("{} Index {} Weight".format(ticker, index.title()))) \
                                    .alias("{} Index {} {} Spot".format(ticker, index.title(), column_price)))
                index_dimensions = []
                for index in indexes:
                    index_dimensions.append("Index {} Weight".format(index))
                    for column_price in DIMENSIONS_PRICE:
                        index_dimensions.append("Index {} {} Spot".format(index, column_price))
                for ticker in tickers:
                    for index in indexes:
                        equity_database_df = equity_database_df.with_columns(
                            pl.when(pl.col("{} Index {} Price Close Spot".format(ticker, index)).is_null()).then(None) \
                                .otherwise(pl.col(["{} {}".format(ticker, dimension)
                                                   for dimension in index_dimensions])).name.keep())
                _equity_print(equity_database_df, _dimensions=index_dimensions,
                              print_label="Equity_Index_Weights", print_verb="added index weights", started=started_time)



                # TODO: Move to aggregate
                started_time = time.time()
                for index in indexes:
                    for column_price in DIMENSIONS_PRICE:
                        column = "{} {}".format(index, column_price)
                        columns = ["{} Index {} {} Spot".format(ticker_index_component, index.title(), column_price) \
                                   for ticker_index_component in tickers]
                        equity_database_df = equity_database_df.with_columns(
                            equity_database_df.select(pl.col(columns)).sum(axis=1).alias(column))
                        equity_database_df = equity_database_df.with_columns(
                            pl.when(pl.col(column) == 0).then(None).otherwise(pl.col(column)).name.keep())
                        for column_price_type in DIMENSIONS_PRICE_TYPES:
                            equity_database_df = equity_database_df.with_columns(
                                pl.col(column).alias("{} {}".format(column, column_price_type)))
                    column = "{} Price Close".format(index)
                    equity_database_df = equity_database_df.with_columns([
                        pl.when(pl.col(column).is_null()).then(None).otherwise(pl.lit(0.0)).alias("{} Market Volume".format(index)),
                        pl.when(pl.col(column).is_null()).then(None).otherwise(pl.lit(0.0)).alias("{} Paid Dividends".format(index)),
                        pl.when(pl.col(column).is_null()).then(None).otherwise(pl.lit(0.0)).alias("{} Stock Splits".format(index)),
                        pl.when(pl.col(column).is_null()).then(None).otherwise(pl.lit("AUD")).alias("{} Currency Base".format(index)),
                        pl.when(pl.col(column).is_null()).then(None).otherwise(pl.lit(1.0)).alias("{} Currency Rate Base".format(index)),
                        pl.when(pl.col(column).is_null()).then(None).otherwise(pl.lit(1.0)).alias("{} Currency Rate Spot".format(index)),
                    ])
                _equity_print(equity_database_df.select(
                    ["Date"] + [column for column in equity_database_df.columns for index in indexes if column.startswith(index)]),
                    _dimensions=DIMENSIONS_PRICE_AUX_TYPES, print_label="Equity_Indexes", print_verb="added indexes", started=started_time)







                # TODO: Move to pre-state
                started_time = time.time()
                for ticker in tickers + indexes:
                    equity_database_df = equity_database_df.with_columns( \
                        (pl.col("{} Market Volume".format(ticker)) *
                         pl.col("{} Price Close Spot".format(ticker))) \
                            .alias("{} Market Volume Spot".format(ticker)))
                _equity_print(equity_database_df, _dimensions=["Price Close Spot", "Market Volume", "Market Volume Spot"],
                              print_label="Equity_Volumes", print_verb="added market volumes", started=started_time)






                # TODO: Move to aggregate
                started_time = time.time()
                for ticker in tickers + indexes:
                    for price_type in [""] + ["{} ".format(dimension) for dimension in DIMENSIONS_PRICE_TYPES]:
                        for change_period in DIMENSIONS_CHANGE_PERIODS:
                            dimension_price = "Price Close {}".format(price_type).strip()
                            dimension_diff = "Price Close {}{}d-Change Absolute".format(price_type, change_period)
                            dimension_percentage = "Price Close {}{}d-Change Percentage".format(price_type, change_period)
                            equity_database_df = equity_database_df.with_columns(
                                pl.when(pl.col("{} Price Close".format(ticker)).is_null()).then(None) \
                                    .otherwise(pl.col("{} {}".format(ticker, dimension_price)) \
                                               .diff(change_period).fill_nan(None)) \
                                    .alias("{} {}".format(ticker, dimension_diff)))
                            equity_database_df = equity_database_df.with_columns(
                                pl.when(pl.col("{} Price Close".format(ticker)).is_not_null() & \
                                        pl.col("{} {}".format(ticker, dimension_diff)).is_null()).then(pl.lit(0.0)) \
                                    .otherwise(pl.col("{} {}".format(ticker, dimension_diff))).name.keep())
                            equity_database_df = equity_database_df.with_columns(
                                pl.when(pl.col("{} Price Close".format(ticker)).is_null()).then(None) \
                                    .otherwise(pl.col("{} {}".format(ticker, dimension_price)) \
                                               .pct_change(change_period).fill_nan(None) * 100) \
                                    .alias("{} {}".format(ticker, dimension_percentage)))
                            equity_database_df = equity_database_df.with_columns(
                                pl.when(pl.col("{} Price Close".format(ticker)).is_not_null() & \
                                        pl.col("{} {}".format(ticker, dimension_percentage)).is_null()).then(pl.lit(0.0)) \
                                    .otherwise(pl.col("{} {}".format(ticker, dimension_percentage))).name.keep())
                _equity_print(equity_database_df,
                              _dimensions=sorted(["Price Close Base", "Price Close Spot"] + DIMENSIONS_CHANGE),
                              print_label="Equity_Changes", print_verb="added price changes", started=started_time)





                # TODO: Work off delta
                started_time = time.time()
                dimensions = []
                dimensions_metadata = [(
                    [
                        "Market Volume Spot",
                        "Price Close",
                        "Price Close Base",
                        "Price Close Spot",
                    ], "$", "1d")]
                for change_period in DIMENSIONS_CHANGE_PERIODS:
                    dimensions_metadata.append((
                        [
                            "Price Close {}d-Change Percentage".format(change_period),
                            "Price Close Base {}d-Change Percentage".format(change_period),
                            "Price Close Spot {}d-Change Percentage".format(change_period),
                        ], "%", "{}d".format(change_period)))
                for dimension_metadata in dimensions_metadata:
                    dimensions.extend(dimension_metadata[0])
                tickers = _equity_tickers(equity_database_df)
                equity_database_df = _equity_clean(equity_database_df)
                equity_database_df = equity_database_df \
                    .select(["Date"] + ["{} {}".format(ticker, dimension) \
                                        for ticker in tickers for dimension in dimensions])
                _equity_print(equity_database_df, _dimensions=dimensions,
                              print_label="Equity", print_verb="cleaned up", started=started_time)
                started_time = time.time()
                for dimension_metadata in dimensions_metadata:
                    for column in dimension_metadata[0]:
                        for ticker in tickers:
                            self.stdout_write(
                                self.dataframe_to_lineprotocol(
                                    equity_database_df.select(
                                        ["Date"] + ["{} {}".format(ticker, dimension) \
                                                    for dimension in dimensions]).drop_nulls(),
                                    tags={
                                        "type": column.replace(" ", "-").lower(),
                                        "period": dimension_metadata[2],
                                        "unit": dimension_metadata[1]
                                    }, print_label="Equity_{}".format(
                                        column.replace(" ", "_").replace("-", "_"))))
                self.print_log("LineProtocol [Equity] serialised", started=started_time)
        except Exception as exception:
            self.print_log("Unexpected error processing equity data", exception=exception)
            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED,
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED) +
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED) -
                             self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED))
        if not len(equity_delta_df):
            self.print_log("No new data found")
        self.counter_write()

    def __init__(self):
        super(Equity, self).__init__("Equity", "1wDj18Imc3q1UWfRDU-h9-Rwb73R6PAm-")
