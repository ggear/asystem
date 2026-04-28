import calendar
import time
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

DIMENSIONS_STATE = (
        ["Market Volume Spot", "Price Close", "Price Close Base", "Price Close Spot", "Currency Rate Base"]
        + ["Price Close {}{}d-Change Percentage".format(pt, period)
           for period in DIMENSIONS_CHANGE_PERIODS for pt in ["", "Base ", "Spot "]]
)

STATEMENT_ATTRIBUTES = ("Date", "Type", "Owner", "Currency", "Rate", "Units", "Value")

STOCK = {
    'AORD': {"start": "1985-01", "end of day": "16:00", "prefix": "^", "exchange": "", },
    'SIG': {"start": "2006-01", "end of day": "16:00", "prefix": "", "exchange": "AX", },
    'WDS': {"start": "2009-01", "end of day": "16:00", "prefix": "", "exchange": "AX", },
    'GOLD': {"start": "2008-01", "end of day": "16:00", "prefix": "", "exchange": "AX", },
    'VAS': {"start": "2010-01", "end of day": "16:00", "prefix": "", "exchange": "AX", },
    'VHY': {"start": "2011-01", "end of day": "16:00", "prefix": "", "exchange": "AX", },
    'MVW': {"start": "2014-06", "end of day": "16:00", "prefix": "", "exchange": "AX", },
    'VGS': {"start": "2014-12", "end of day": "16:00", "prefix": "", "exchange": "AX", },
    'VGE': {"start": "2014-01", "end of day": "16:00", "prefix": "", "exchange": "AX", },
    'NDQ': {"start": "2015-06", "end of day": "16:00", "prefix": "", "exchange": "AX", },
    'VAE': {"start": "2016-01", "end of day": "16:00", "prefix": "", "exchange": "AX", },
    'VDHG': {"start": "2018-01", "end of day": "16:00", "prefix": "", "exchange": "AX", },
    'IAF': {"start": "2012-04", "end of day": "16:00", "prefix": "", "exchange": "AX", },
    'ACDC': {"start": "2018-09", "end of day": "16:00", "prefix": "", "exchange": "AX", },
    'CLNE': {"start": "2021-04", "end of day": "16:00", "prefix": "", "exchange": "AX", },
    'ERTH': {"start": "2021-04", "end of day": "16:00", "prefix": "", "exchange": "AX", },
    'QSML': {"start": "2021-05", "end of day": "16:00", "prefix": "", "exchange": "AX", },
    'GAME': {"start": "2022-05", "end of day": "16:00", "prefix": "", "exchange": "AX", },
    'URNM': {"start": "2022-07", "end of day": "16:00", "prefix": "", "exchange": "AX", },
}

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
                                    "{}{}{}{}".format(STOCK[stock]["prefix"], stock, '.' if STOCK[stock]["exchange"] != "" else '', STOCK[stock]["exchange"]),
                                    "{}-{:02}-01".format(year, month),
                                    "{}-{:02}-{:02}".format(
                                        year,
                                        month,
                                        calendar.monthrange(year, month)[1]),
                                    STOCK[stock]["end of day"], check=year == today.year and month == today.month)
                    else:
                        start_month = stock_start.month if year == stock_start.year else 1
                        file_name = "{}/Yahoo_{}_{}.csv".format(self.input, stock, year)
                        stock_files[file_name] = self.stock_download(
                            file_name,
                            "{}{}{}{}".format(STOCK[stock]["prefix"], stock, '.' if STOCK[stock]["exchange"] != "" else '', STOCK[stock]["exchange"]),
                            "{}-{:02}-01".format(year, start_month),
                            "{}-{:02}-{:02}".format(year, 12, 31),
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
        self.print_log("Files [Equity] downloaded or cached [{}] stock and [{}] fund files".format(len(stock_files), len(statement_files)), started=started_time)
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
                        stock_new_names = ["Date"] + ["{} {}".format(stock_ticker, column) for column in DIMENSIONS_PRICE_AUX]
                        stock_df = stock_df.rename(dict(zip(stock_df.columns, stock_new_names)))
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
                            statement_data[statement_file_name]['Parse'] = []
                            parse_lines = statement_data[statement_file_name]['Parse']
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
                                    statement_line = statement_lines[line_index].strip()
                                    statement_tokens = statement_line.split()
                                    parse_line = "File [{}]: Page [{:02d}]: Line [{:02d}]:  ".format(
                                        basename(statement_file_name), page_index, line_index)
                                    parse_line += " ".join("{:02d}:{}".format(i, t) for i, t in enumerate(statement_tokens))
                                    parse_lines.append(parse_line)
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
                                            for index_spec in [
                                                (2, "Situations", CURRENCIES, 5, 10, 2, 6),
                                                (2, "Situations", CURRENCIES, 8, 13, 2, 6),
                                                # Format changed from "Compass Offshore Special Situations PCC Ltd GBP"
                                                # to "Compass Offshore Special Situations ICAV GBP" in 58861-A-122025-1.pdf
                                                (2, "Situations", CURRENCIES, 7, 12, 1, 6),
                                                (3, "Situations", CURRENCIES, 5, 9, 2, 6),
                                                (2, "Shares", ["USD"], 2, 7),
                                                (3, "Shares", ["USD"], 2, 6),
                                            ]:
                                                if page_index == index_spec[0] and index_spec[1] in statement_line:
                                                    for currency in index_spec[2]:
                                                        if index_spec[1] == "Shares" or currency in statement_line:
                                                            try:
                                                                statement_position = {
                                                                    "Date": statement_date.strftime('%Y-%m-%d'),
                                                                    "Type": statement_type.strip(),
                                                                    "Owner": statement_owner,
                                                                    "Currency": currency,
                                                                    "Rate": statement_rates[currency],
                                                                    "Units": float(statement_tokens
                                                                                   [index_spec[3]].replace(',', '')),
                                                                    "Value": float(statement_tokens
                                                                                   [index_spec[4]].replace(',', ''))
                                                                }
                                                                if index_spec[1] == "Situations":
                                                                    if line_index < (len(statement_lines) - 1) and \
                                                                            statement_lines[line_index + 1].strip().startswith("PCC"):
                                                                        currency = statement_lines[line_index + 1].strip().split()[
                                                                            index_spec[5]]
                                                                    else:
                                                                        currency = statement_tokens[index_spec[6]]
                                                                statement_position["Ticker"] = \
                                                                    'MCK' if statement_owner == 'Jane' \
                                                                             and currency == 'USD' else \
                                                                        'MUS' if statement_owner == 'Joint' \
                                                                                 and currency == 'USD' else \
                                                                            'MUK' if statement_owner == 'Joint' \
                                                                                     and currency == 'GBP' else \
                                                                                'MSG' if statement_owner == 'Joint' \
                                                                                         and currency == 'SGD' else \
                                                                                    'UNKNOWN'
                                                                statement_data[statement_file_name]["Positions"] \
                                                                    [str(statement_type + currency)] = statement_position
                                                            except (KeyError, IndexError, ValueError, AttributeError) as parse_exception:
                                                                statement_data[statement_file_name]["Errors"].append(
                                                                    "Position parse skipped at page [{}] line [{}] for currency [{}]: {}: {}".format(
                                                                        page_index, line_index, currency,
                                                                        type(parse_exception).__name__, parse_exception))
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
                        if len(statement_positions) == 0:
                            statement_data[statement_file_name]['Status'] = STATUS_FAILURE
                            statement_data[statement_file_name]["Errors"] \
                                .append("Statement parse failed to resolve all keys {} in {}"
                                        .format(STATEMENT_ATTRIBUTES, {}))
                        for statement_position in list(statement_positions.values()):
                            if not all(key in statement_position for key in STATEMENT_ATTRIBUTES):
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
            _tickers = _equity_tickers(_equity_df)
            _mask_exprs = [
                pl.when(pl.col("{} Price Close".format(_ticker)).is_null()).then(None) \
                    .otherwise(pl.col(_equity_columns(_equity_df, _ticker))).name.keep()
                for _ticker in _tickers
            ]
            if _mask_exprs:
                _equity_df = _equity_df.with_columns(_mask_exprs)
            _equity_df = _equity_df.filter(pl.col("Date").is_not_null()) \
                .filter(~pl.all_horizontal(pl.all().exclude("Date").is_null())) \
                .sort("Date").set_sorted("Date")
            return _equity_df

        def _equity_upsample(_equity_df):
            return _equity_df \
                .unique(subset=["Date"], keep="first").sort("Date").set_sorted("Date") \
                .upsample(time_column="Date", every="1d").fill_nan(pl.lit(None)) \
                .with_columns(cs.numeric().interpolate()) \
                .with_columns(cs.string().forward_fill())

        def _equity_print(_equity_df, _dimensions=DIMENSIONS_PRICE_AUX, print_label=None, print_verb=None, print_rows=PL_PRINT_ROWS, started=None):
            self.dataframe_print(_equity_df, print_label=print_label, print_verb=print_verb, print_suffix="(data to follow)", print_rows=0, started=started)
            if len(_equity_df) > 0:
                for _ticker in _equity_tickers(_equity_df):
                    _ticker_df = _equity_df.select(["Date"] + \
                                                   ["{} {}".format(_ticker, _dimension) for _dimension in _dimensions
                                                    if "{} {}".format(_ticker, _dimension) in _equity_df.columns]) \
                        .fill_nan(None).filter(~pl.all_horizontal(pl.all().exclude("Date").is_null()))
                    self.dataframe_print(_ticker_df, print_label="{}_{}".format(print_label, _ticker), print_verb=print_verb, print_rows=print_rows)

        fx_rates = {}
        indexes = []

        try:
            if new_data:
                started_time = time.time()
                statements_positions = []
                for file_name in statement_data:
                    if statement_data[file_name]['Status'] == STATUS_SUCCESS:
                        statement_position = statement_data[file_name]["Positions"]
                        statements_positions.extend(list(statement_position.values()))
                        self.print_log("File [{}] processed as [{}] with positions {}".format(basename(file_name), STATUS_SUCCESS, list(statement_position.keys())))
                    elif statement_data[file_name]['Status'] == STATUS_SKIPPED:
                        self.print_log("File [{}] processed as [{}]".format(basename(file_name), STATUS_SKIPPED))
                    else:
                        self.print_log("File [{}] processed as [{}] at parsing point:".format(basename(file_name), STATUS_FAILURE))
                        self.print_log(statement_data[file_name]["Parse"])
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
                    ).pivot(values=["Price", "Rate", "Currency"], index="Date", on="Ticker").sort("Date")
                    self.dataframe_print(statement_df, print_label="Funds", print_verb="pivoted", started=started_time)
                    started_time = time.time()
                    rename_map = {}
                    for statement_column in statement_df.columns:
                        if statement_column.startswith("Price_"):
                            rename_map[statement_column] = "{} Price Close".format(statement_column.replace("Price_", "", 1))
                        elif statement_column.startswith("Rate_"):
                            rename_map[statement_column] = "{} Currency Rate Base".format(statement_column.replace("Rate_", "", 1))
                        elif statement_column.startswith("Currency_"):
                            rename_map[statement_column] = "{} Currency Base".format(statement_column.replace("Currency_", "", 1))
                    statement_df = statement_df.rename(rename_map)
                    self.dataframe_print(statement_df, print_label="Funds", print_verb="renamed", started=started_time)
                    started_time = time.time()
                    statement_exprs = []
                    for ticker in tickers:
                        statement_exprs.extend([
                            pl.col("{} Price Close".format(ticker)).alias("{} Price Open".format(ticker)),
                            pl.col("{} Price Close".format(ticker)).alias("{} Price High".format(ticker)),
                            pl.col("{} Price Close".format(ticker)).alias("{} Price Low".format(ticker)),
                            pl.lit(0, pl.Int64).alias("{} Market Volume".format(ticker)),
                            pl.lit(0.0, pl.Float64).alias("{} Paid Dividends".format(ticker)),
                            pl.lit(0.0, pl.Float64).alias("{} Stock Splits".format(ticker)),
                        ])
                    if statement_exprs:
                        statement_df = statement_df.with_columns(statement_exprs)
                    statement_df = statement_df.select(["Date"] + ["{} {}".format(ticker, dimension) for ticker in tickers for dimension in DIMENSIONS_PRICE_AUX])
                    statement_df = _equity_upsample(statement_df)
                    statement_df = _equity_clean(statement_df)
                _equity_print(statement_df, print_label="Funds", print_verb="enriched", started=started_time)
                started_time = time.time()
                for stock in STOCK:
                    if stock in stocks_df:
                        equity_df = equity_df.join(stocks_df[stock], on="Date", how="full", coalesce=True)
                equity_df = _equity_upsample(equity_df)
                _equity_print(equity_df, print_label="Stocks", print_verb="concatenated", started=started_time)
                started_time = time.time()
                equity_df = equity_df.join(statement_df, on="Date", how="full", coalesce=True)
                equity_df = equity_df.unique(subset=["Date"], keep="first").sort("Date").set_sorted("Date")
                _equity_print(equity_df, print_label="Equity", print_verb="concatenated", started=started_time)
                started_time = time.time()
                equity_df_manual = self.sheet_download("Manual_Stock_Prices_Sheet", DRIVE_KEY_PRICES, sheet_name="Manual", schema={"Date": pl.Date})
                equity_df_manual = _equity_upsample(equity_df_manual)
                tickers_manual = _equity_tickers(equity_df_manual)
                manual_exprs = []
                for ticker in tickers_manual:
                    manual_exprs.extend([
                        pl.col("{} Price Close".format(ticker)).alias("{} Price Open".format(ticker)),
                        pl.col("{} Price Close".format(ticker)).alias("{} Price High".format(ticker)),
                        pl.col("{} Price Close".format(ticker)).alias("{} Price Low".format(ticker)),
                        pl.lit(0, pl.Int64).alias("{} Market Volume".format(ticker)),
                        pl.lit(0.0, pl.Float64).alias("{} Paid Dividends".format(ticker)),
                        pl.lit(0.0, pl.Float64).alias("{} Stock Splits".format(ticker)),
                        pl.lit("AUD").alias("{} Currency Base".format(ticker)),
                    ])
                if manual_exprs:
                    equity_df_manual = equity_df_manual.with_columns(manual_exprs)
                equity_df_manual = _equity_clean(equity_df_manual)
                _equity_print(equity_df_manual, print_label="Equity_Manual_Stock_Prices", print_verb="processed", started=started_time)
                started_time = time.time()
                tickers = _equity_tickers(equity_df)
                new_ticker_dfs = []
                for ticker in tickers_manual:
                    ticker_cols = ["Date"] + [c for c in equity_df_manual.columns if c.startswith(ticker + " ")]
                    ticker_df = equity_df_manual.select(ticker_cols)
                    if ticker in tickers:
                        equity_df = equity_df.update(ticker_df, on="Date", how="full")
                    else:
                        new_ticker_dfs.append(ticker_df)
                if new_ticker_dfs:
                    equity_df = pl.concat([equity_df] + new_ticker_dfs, how="align")
                equity_df = _equity_upsample(equity_df)
                tickers = _equity_tickers(equity_df)
                equity_df = equity_df.select(
                    ["Date"] + ["{} {}".format(ticker, dimension) for ticker in tickers for dimension in DIMENSIONS_PRICE_AUX])
                equity_df = _equity_clean(equity_df)
                _equity_print(equity_df, print_label="Equity", print_verb="added manual stock prices", started=started_time)
                started_time = time.time()
                columns = []
                missing_exprs = []
                existing_cols = set(equity_df.columns)
                for ticker in tickers:
                    for dimension_diff in DIMENSIONS_PRICE_AUX:
                        column = "{} {}".format(ticker, dimension_diff)
                        columns.append(column)
                        if column not in existing_cols:
                            if "Price" in dimension_diff:
                                missing_exprs.append(pl.col("{} Price Close".format(ticker)).alias(column))
                            elif dimension_diff == "Market Volume":
                                missing_exprs.append(pl.lit(0, pl.Int64).alias(column))
                            elif dimension_diff in ["Paid Dividends", "Stock Splits"]:
                                missing_exprs.append(pl.lit(0.0, pl.Float64).alias(column))
                            elif dimension_diff == "Currency Rate Base":
                                missing_exprs.append(pl.lit(1.0, pl.Float64).alias(column))
                            elif dimension_diff == "Currency Base":
                                missing_exprs.append(pl.lit("AUD", pl.Utf8).alias(column))
                if missing_exprs:
                    equity_df = equity_df.with_columns(missing_exprs)
                equity_df = equity_df.select(["Date"] + columns).sort("Date")
                _equity_print(equity_df, print_label="Equity", print_verb="sorted", started=started_time)

                # MOVED: Apply FX rates and compute spot prices
                started_time = time.time()
                equity_df = _equity_clean(equity_df)
                tickers = _equity_tickers(equity_df)
                if len(equity_df) > 0:
                    started_fx = pytz.UTC.localize(datetime.combine(equity_df.head(1).rows()[0][0], datetime.min.time())).isoformat()
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
                        self.database_download(fx_file, fx_query, check=library.test(library.WRANGLE_DISABLE_FILE_DOWNLOAD))
                        fx_rates[fx_pair] = self.csv_read(fx_file, schema={"Date": pl.Date})
                        fx_rates[fx_pair] = _equity_upsample(fx_rates[fx_pair])
                    aud_rate_exprs = []
                    spot_exprs = []
                    for ticker in tickers:
                        base_rows = equity_df.select("{} Currency Base".format(ticker)).drop_nulls().head(1).rows()
                        base_currency = base_rows[0][0] if base_rows else "AUD"
                        if base_currency == "AUD":
                            aud_rate_exprs.append(
                                pl.when(pl.col("{} Price Close".format(ticker)).is_null()).then(None) \
                                    .otherwise(pl.lit(1.0)).alias("{} Currency Rate Spot".format(ticker)))
                        else:
                            equity_df = equity_df.join(fx_rates[base_currency], on="Date", how="full", coalesce=True) \
                                .with_columns(pl.col("Rate").alias("{} Currency Rate Spot".format(ticker))).drop("Rate")
                        for column_price in DIMENSIONS_PRICE:
                            for column_price_type in DIMENSIONS_PRICE_TYPES:
                                spot_exprs.append(
                                    (pl.col("{} {}".format(ticker, column_price)) *
                                     pl.col("{} Currency Rate {}".format(ticker, column_price_type))) \
                                        .alias("{} {} {}".format(ticker, column_price, column_price_type)))
                    if aud_rate_exprs:
                        equity_df = equity_df.with_columns(aud_rate_exprs)
                    if spot_exprs:
                        equity_df = equity_df.with_columns(spot_exprs)
                    equity_df = equity_df.select(["Date"] + ["{} {}".format(ticker, column) for ticker in sorted(tickers) for column in DIMENSIONS_PRICE_AUX_TYPES])
                    rate_mask_exprs = [
                        pl.when(pl.col("{} Price Close".format(ticker)).is_null()).then(None).otherwise(pl.col("{} Currency Rate Spot".format(ticker))).name.keep()
                        for ticker in tickers
                    ]
                    if rate_mask_exprs:
                        equity_df = equity_df.with_columns(rate_mask_exprs)
                _equity_print(equity_df, _dimensions=DIMENSIONS_PRICE_AUX_TYPES, print_label="Equity", print_verb="added FX rates", started=started_time)

                # MOVED: Download index weights and apply to equity_df
                index_weights = self.sheet_download("Index_Weights_Sheet", DRIVE_KEY_PORTFOLIO, sheet_name="Indexes", sheet_start_row=2)
                started_time = time.time()
                indexes = sorted([column.removesuffix(" Quantity") for column in index_weights.columns if column.endswith(" Quantity")])
                index_weights = index_weights \
                    .select(["Exchange Symbol"] + ["{} Quantity".format(index) for index in indexes]).drop_nulls()
                index_weights = index_weights.rename(
                    dict(zip(index_weights.columns, ["Ticker"] + indexes)))
                index_weights = index_weights.unique(subset=["Ticker"], keep="first").sort("Ticker").set_sorted("Ticker")
                self.dataframe_print(index_weights, print_label="Index_Weights_Sheet",
                                     print_verb="processed", print_rows=1000, started=started_time)
                started_time = time.time()
                weight_exprs = []
                spot_exprs = []
                for ticker in tickers:
                    for index in indexes:
                        index_title = index.title()
                        weight_rows = index_weights.filter((pl.col("Ticker") == ticker)).select([index]).head(1).rows()
                        weight_exprs.append(
                            pl.lit(weight_rows[0][0] if len(weight_rows) > 0 else 0.0) \
                                .alias("{} Index {} Weight".format(ticker, index_title)))
                if weight_exprs:
                    equity_df = equity_df.with_columns(weight_exprs)
                for ticker in tickers:
                    for index in indexes:
                        index_title = index.title()
                        for column_price in DIMENSIONS_PRICE:
                            spot_exprs.append(
                                (pl.col("{} {} Spot".format(ticker, column_price)) *
                                 pl.col("{} Index {} Weight".format(ticker, index_title))) \
                                    .alias("{} Index {} {} Spot".format(ticker, index_title, column_price)))
                if spot_exprs:
                    equity_df = equity_df.with_columns(spot_exprs)
                index_dimensions = []
                for index in indexes:
                    index_title = index.title()
                    index_dimensions.append("Index {} Weight".format(index_title))
                    for column_price in DIMENSIONS_PRICE:
                        index_dimensions.append("Index {} {} Spot".format(index_title, column_price))
                if indexes:
                    last_index_title = indexes[-1].title()
                    mask_exprs = [
                        pl.when(pl.col("{} Index {} Price Close Spot".format(ticker, last_index_title)).is_null()).then(None) \
                            .otherwise(pl.col(["{} {}".format(ticker, dimension)
                                               for dimension in index_dimensions])).name.keep()
                        for ticker in tickers
                    ]
                    if mask_exprs:
                        equity_df = equity_df.with_columns(mask_exprs)
                _equity_print(equity_df, _dimensions=index_dimensions, print_label="Equity_Index_Weights", print_verb="added index weights", started=started_time)

                started_time = time.time()
                volume_exprs = [
                    (pl.col("{} Market Volume".format(ticker)) *
                     pl.col("{} Price Close Spot".format(ticker))) \
                        .alias("{} Market Volume Spot".format(ticker))
                    for ticker in tickers
                ]
                if volume_exprs:
                    equity_df = equity_df.with_columns(volume_exprs)
                _equity_print(equity_df, _dimensions=["Price Close Spot", "Market Volume", "Market Volume Spot"], print_label="Equity_Volumes", print_verb="added market volumes", started=started_time)

        except Exception as exception:
            self.print_log("Unexpected error processing equity dataframe", exception=exception)
            processed = self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
            skipped = self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED)
            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED, -processed)
            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED, -skipped)
            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED, processed + skipped)
        try:
            def _make_aggregate(_indexes):
                def _aggregate_function(_data_df):
                    # All-null float columns are inferred as String after CSV round-trip; restore Float64
                    _str_cols = [c for c, t in zip(_data_df.columns, _data_df.dtypes)
                                 if str(t) in ('String', 'Utf8', 'Null') and c != 'Date']
                    if _str_cols:
                        _data_df = _data_df.with_columns(
                            [pl.col(c).cast(pl.Float64, strict=False) for c in _str_cols])
                    _tickers = _equity_tickers(_data_df)

                    # Index aggregations (guarded: skip if index price columns already present)
                    for _index in _indexes:
                        _index_title = _index.title()
                        for _column_price in DIMENSIONS_PRICE:
                            _column = "{} {}".format(_index, _column_price)
                            if _column not in _data_df.columns:
                                _index_cols = ["{} Index {} {} Spot".format(_t, _index_title, _column_price)
                                               for _t in _tickers
                                               if "{} Index {} {} Spot".format(_t, _index_title, _column_price) in _data_df.columns]
                                if len(_index_cols) > 0:
                                    _data_df = _data_df.with_columns(pl.sum_horizontal(_index_cols).alias(_column))
                                    _data_df = _data_df.with_columns(
                                        pl.when(pl.col(_column) == 0).then(None).otherwise(pl.col(_column)).name.keep())
                                for _column_price_type in DIMENSIONS_PRICE_TYPES:
                                    _col_typed = "{} {}".format(_column, _column_price_type)
                                    if _col_typed not in _data_df.columns and _column in _data_df.columns:
                                        _data_df = _data_df.with_columns(pl.col(_column).alias(_col_typed))
                        _column_close = "{} Price Close".format(_index)
                        if _column_close in _data_df.columns and "{} Market Volume".format(_index) not in _data_df.columns:
                            _data_df = _data_df.with_columns([
                                pl.when(pl.col(_column_close).is_null()).then(None).otherwise(pl.lit(0.0)).alias("{} Market Volume".format(_index)),
                                pl.when(pl.col(_column_close).is_null()).then(None).otherwise(pl.lit(0.0)).alias("{} Paid Dividends".format(_index)),
                                pl.when(pl.col(_column_close).is_null()).then(None).otherwise(pl.lit(0.0)).alias("{} Stock Splits".format(_index)),
                                pl.when(pl.col(_column_close).is_null()).then(None).otherwise(pl.lit("AUD")).alias("{} Currency Base".format(_index)),
                                pl.when(pl.col(_column_close).is_null()).then(None).otherwise(pl.lit(1.0)).alias("{} Currency Rate Base".format(_index)),
                                pl.when(pl.col(_column_close).is_null()).then(None).otherwise(pl.lit(1.0)).alias("{} Currency Rate Spot".format(_index)),
                            ])

                    # Market volume spot for indexes (guarded: skip if already present)
                    _mvs_exprs = []
                    for _index in _indexes:
                        _mvs_col = "{} Market Volume Spot".format(_index)
                        if _mvs_col not in _data_df.columns and \
                                "{} Market Volume".format(_index) in _data_df.columns and \
                                "{} Price Close Spot".format(_index) in _data_df.columns:
                            _mvs_exprs.append(
                                (pl.col("{} Market Volume".format(_index)) *
                                 pl.col("{} Price Close Spot".format(_index)))
                                .alias(_mvs_col))
                    if _mvs_exprs:
                        _data_df = _data_df.with_columns(_mvs_exprs)

                    # Price changes for all tickers and indexes (two-pass: create, then mask)
                    _create_exprs = []
                    _mask_specs = []
                    for _ticker in _equity_tickers(_data_df):
                        for _price_type in [""] + ["{} ".format(_dimension) for _dimension in DIMENSIONS_PRICE_TYPES]:
                            for _change_period in DIMENSIONS_CHANGE_PERIODS:
                                _dimension_price = "Price Close {}".format(_price_type).strip()
                                _dimension_diff = "Price Close {}{}d-Change Absolute".format(_price_type, _change_period)
                                _dimension_percentage = "Price Close {}{}d-Change Percentage".format(_price_type, _change_period)
                                _price_col = "{} {}".format(_ticker, _dimension_price)
                                if _price_col in _data_df.columns:
                                    _diff_col = "{} {}".format(_ticker, _dimension_diff)
                                    _pct_col = "{} {}".format(_ticker, _dimension_percentage)
                                    _create_exprs.extend([
                                        pl.when(pl.col("{} Price Close".format(_ticker)).is_null()).then(None) \
                                            .otherwise(pl.col(_price_col).diff(_change_period).fill_nan(None)) \
                                            .alias(_diff_col),
                                        pl.when(pl.col("{} Price Close".format(_ticker)).is_null()).then(None) \
                                            .otherwise(pl.col(_price_col).pct_change(_change_period).fill_nan(None) * 100) \
                                            .alias(_pct_col),
                                    ])
                                    _mask_specs.append((_ticker, _diff_col))
                                    _mask_specs.append((_ticker, _pct_col))
                    if _create_exprs:
                        _data_df = _data_df.with_columns(_create_exprs)
                    if _mask_specs:
                        _data_df = _data_df.with_columns([
                            pl.when(pl.col("{} Price Close".format(_t)).is_not_null() & \
                                    pl.col(_c).is_null()).then(pl.lit(0.0)) \
                                .otherwise(pl.col(_c)).name.keep()
                            for _t, _c in _mask_specs
                        ])

                    # Select final output columns for state storage
                    _all_tickers = _equity_tickers(_data_df)
                    _columns = []
                    for _t in sorted(_all_tickers):
                        for _d in DIMENSIONS_STATE:
                            _col = "{} {}".format(_t, _d)
                            if _col in _data_df.columns:
                                _columns.append(_col)
                    return _data_df.select(["Date"] + _columns).with_columns(cs.float().round(4))

                return _aggregate_function

            equity_delta_df, equity_current_df, _ = self.state_cache(equity_df, _make_aggregate(indexes))
            if len(equity_delta_df):

                # Sheet upload using full current history
                started_time = time.time()
                dimensions_sheet = ["Price Close", "Currency Rate Base"]
                tickers = _equity_tickers(equity_current_df)
                equity_sheet_df = equity_current_df.select(["Date"] + ["{} {}".format(ticker, dimension) for ticker in tickers for dimension in dimensions_sheet])
                equity_sheet_df = equity_sheet_df.filter(pl.col("Date") > pl.lit(datetime(2007, 1, 1))).sort("Date", descending=True)
                _equity_print(equity_sheet_df, _dimensions=dimensions_sheet, print_label="Sheet", print_verb="filtered", started=started_time)
                self.sheet_upload(equity_sheet_df, DRIVE_KEY_PRICES, sheet_name='History')

                # Line protocol output from equity_delta_df
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
                tickers = _equity_tickers(equity_delta_df)
                equity_output_df = _equity_clean(equity_delta_df)
                equity_output_df = equity_output_df \
                    .select(["Date"] + ["{} {}".format(ticker, dimension) \
                                        for ticker in tickers for dimension in dimensions
                                        if "{} {}".format(ticker, dimension) in equity_output_df.columns])
                _equity_print(equity_output_df, _dimensions=dimensions, print_label="Equity", print_verb="cleaned up", started=started_time)
                started_time = time.time()
                for dimension_metadata in dimensions_metadata:
                    for column in dimension_metadata[0]:
                        for ticker in tickers:
                            self.stdout_write(
                                self.dataframe_to_lineprotocol(
                                    equity_output_df.select(
                                        ["Date"] + ["{} {}".format(ticker, dimension) \
                                                    for dimension in dimensions
                                                    if "{} {}".format(ticker, dimension) in equity_output_df.columns]).drop_nulls(),
                                    tags={
                                        "type": column.replace(" ", "-").lower(),
                                        "period": dimension_metadata[2],
                                        "unit": dimension_metadata[1]
                                    }, print_label="Equity_{}".format(column.replace(" ", "_").replace("-", "_"))))
                self.print_log("LineProtocol [Equity] serialised", started=started_time)
        except Exception as exception:
            self.print_log("Unexpected error processing equity data", exception=exception)
            processed = self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED)
            skipped = self.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED)
            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_PROCESSED, -processed)
            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_SKIPPED, -skipped)
            self.add_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED, processed + skipped)
        if not len(equity_delta_df):
            self.print_log("No new data found")
        self.counter_write()

    def __init__(self):
        super(Equity, self).__init__("Equity", "1wDj18Imc3q1UWfRDU-h9-Rwb73R6PAm-")
