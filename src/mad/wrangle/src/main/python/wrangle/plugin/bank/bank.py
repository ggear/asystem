import glob
import hashlib
import os
import re
import time
import uuid
from datetime import date, datetime, timedelta
from datetime import time as day_time
from os.path import abspath, basename, dirname, getmtime, isfile, join
from typing import cast

import polars as pl
import polars.selectors as cs

from wrangle import plugin
from wrangle.plugin import PL_PRINT_ROWS
from wrangle.plugin.logger import dataframe_print

FILE_NAME_PATTERN = r"^(redbark|manual)_(balances|transactions)_(\d{4})\.csv$"
RECORD_ID_SEPARATOR = "\x1f"

FLAG_YES = "Yes"
FLAG_NO = "No"
FLAGS = [FLAG_YES, FLAG_NO]

REDBARK_TYPE_CREDIT = "credit-card"
REDBARK_TIMEZONE = "Australia/Perth"
REDBARK_ACCOUNTS_COLUMNS = ["id", "connectionId", "provider", "name", "type", "institutionName", "accountNumber", "currency"]
REDBARK_BALANCES_COLUMNS = ["accountId", "currentBalance", "availableBalance", "currency", "observedAt", "freshness"]
REDBARK_TRANSACTIONS_COLUMNS = ["id", "accountId", "status", "date", "postDate", "amount", "direction", "description", "category", "merchantCategoryCode"]

ACCOUNTS_CHECK_DAYS = 7
ACCOUNT_STATUS_LINKED = "Linked"
ACCOUNT_STATUS_MISSING = "Missing"
ACCOUNT_STATUS_DUPLICATE = "Duplicate"
ACCOUNT_STATUS_MANUAL = "Manual"
ACCOUNT_STATUS_CLOSED = "Closed"
ACCOUNT_STATUSES = [ACCOUNT_STATUS_LINKED, ACCOUNT_STATUS_MISSING, ACCOUNT_STATUS_DUPLICATE, ACCOUNT_STATUS_MANUAL, ACCOUNT_STATUS_CLOSED]
ACCOUNT_TYPE_ASSET = "Asset"
ACCOUNT_TYPE_LIABILITY = "Liability"
ACCOUNT_TYPES = [ACCOUNT_TYPE_ASSET, ACCOUNT_TYPE_LIABILITY]
ACCOUNT_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "wrangle/account/v1")
ACCOUNTS_TAB_COLUMNS = ["From", "Name", "Institution", "Number", "Type", "Status", "Account ID", "Redbark Account ID", "Redbark Connection ID"]
ACCOUNTS_SCHEMA = {
    "From": pl.Date,
    "Institution": pl.Utf8,
    "Number": pl.Utf8,
    "Name": pl.Utf8,
    "Type": pl.Utf8,
    "Status": pl.Utf8,
    "Redbark Account ID": pl.Utf8,
    "Redbark Connection ID": pl.Utf8,
}

CLASSIFIER_PATTERN_MIN = 2
CLASSIFIER_MATCH_SHARE = 0.2
CLASSIFIER_BANK_CODES = [
    "BANK_FEES",
    "ENTERTAINMENT",
    "FOOD_AND_DRINK",
    "GOVERNMENT_AND_NON_PROFIT",
    "HOME_IMPROVEMENT",
    "INCOME",
    "LOAN_PAYMENTS",
    "MEDICAL",
    "MERCHANDISE",
    "PERSONAL_CARE",
    "RENT_AND_UTILITIES",
    "SERVICES",
    "TRANSFER_IN",
    "TRANSFER_OUT",
    "TRANSPORTATION",
    "TRAVEL",
]
CLASSIFIER_MERCHANT_CODE_NONE = "0000"
CLASSIFIER_SCHEMA = {
    "Category": pl.Utf8,
    "Bucket": pl.Utf8,
    "Budgeted": pl.Utf8,
    "Bank Code": pl.Utf8,
    "Merchant Code": pl.Utf8,
    "Pattern": pl.Utf8,
}

BALANCES_MAX_AGE_HOURS = 3
BALANCES_MANUAL_STALE_DAYS = 35
BALANCES_MANUAL_JUMP = 10
BALANCES_MANUAL_TIME = "23:59:59"
BALANCE_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "wrangle/balance/v2")
BALANCES_BALANCE_FORMULA = '=IF({Balance Manual}<>"",{Balance Manual},{Balance Linked})'
BALANCES_KEY_COLUMNS = ["Date", "Time", "Account ID"]
BALANCES_RAW_COLUMNS = ["Time", "Account", "Account ID", "Balance ID"]
BALANCES_SCHEMA = {
    "Date": pl.Date,
    "Time": pl.Utf8,
    "Account": pl.Utf8,
    "Balance": pl.Float64,
    "Balance Manual": pl.Float64,
    "Balance Linked": pl.Float64,
    "Account ID": pl.Utf8,
    "Balance ID": pl.Utf8,
}
BALANCES_STATE_SCHEMA = {
    "Date": pl.Date,
    "Time": pl.Utf8,
    "Account ID": pl.Utf8,
    "Account": pl.Utf8,
    "Account Institution": pl.Utf8,
    "Account Number": pl.Utf8,
    "Account Type": pl.Utf8,
    "Balance": pl.Float64,
    "Balance Manual": pl.Float64,
    "Balance Linked": pl.Float64,
    "Balance ID": pl.Utf8,
}

TRANSACTIONS_MATCH_DAYS = 3
TRANSACTIONS_LEEWAY_DAYS = 14
TRANSACTIONS_POSTING_DAYS = 7
TRANSACTIONS_HISTORY_DAYS = 7 * 365 - 7
TRANSACTION_PLACEHOLDER_DESCRIPTION = "Null Transaction"
TRANSACTION_PLACEHOLDER = (pl.col("Amount") == 0) & (pl.col("Description") == TRANSACTION_PLACEHOLDER_DESCRIPTION)
TRANSACTION_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "wrangle/transaction/v1")
TRANSACTIONS_CATEGORY_FORMULA = '=IF({Category Manual}<>"",{Category Manual},{Category Derived})'
TRANSACTIONS_BUCKET_FORMULA = '=IFERROR(VLOOKUP({Category},Classifier!A:B,2,FALSE),"")'
TRANSACTIONS_CATEGORY_OPTIONS = "Classifier!A2:A"
TRANSACTIONS_KEY_COLUMNS = ["Date", "Transaction ID", "Split"]
TRANSACTIONS_RAW_COLUMNS = ["Account", "Description", "Bank Code", "Merchant Code", "Vetted", "Category Manual", "Category Derived", "Account ID", "Source ID", "Transaction ID"]
TRANSACTIONS_SCHEMA = {
    "Date": pl.Date,
    "Account": pl.Utf8,
    "Amount": pl.Float64,
    "Amount Split": pl.Float64,
    "Description": pl.Utf8,
    "Bank Code": pl.Utf8,
    "Merchant Code": pl.Utf8,
    "Vetted": pl.Utf8,
    "Category": pl.Utf8,
    "Category Manual": pl.Utf8,
    "Category Derived": pl.Utf8,
    "Account ID": pl.Utf8,
    "Source ID": pl.Utf8,
    "Transaction ID": pl.Utf8,
}
TRANSACTIONS_YEAR_TAB_SCHEMA = {
    "Date": pl.Date,
    "Account": pl.Utf8,
    "Amount": pl.Float64,
    "Amount Split": pl.Float64,
    "Description": pl.Utf8,
    "Bank Code": pl.Utf8,
    "Merchant Code": pl.Utf8,
    "Vetted": pl.Utf8,
    "Category": pl.Utf8,
    "Bucket": pl.Utf8,
    "Category Manual": pl.Utf8,
    "Category Derived": pl.Utf8,
    "Account ID": pl.Utf8,
    "Source ID": pl.Utf8,
    "Transaction ID": pl.Utf8,
}
TRANSACTIONS_STATE_SCHEMA = {
    "Date": pl.Date,
    "Transaction ID": pl.Utf8,
    "Split": pl.Int64,
    "Account": pl.Utf8,
    "Account Institution": pl.Utf8,
    "Account Number": pl.Utf8,
    "Account Type": pl.Utf8,
    "Amount": pl.Float64,
    "Amount Split": pl.Float64,
    "Description": pl.Utf8,
    "Bank Code": pl.Utf8,
    "Merchant Code": pl.Utf8,
    "Vetted": pl.Utf8,
    "Category": pl.Utf8,
    "Bucket": pl.Utf8,
    "Category Manual": pl.Utf8,
    "Category Derived": pl.Utf8,
    "Account ID": pl.Utf8,
    "Source ID": pl.Utf8,
}

TRANSACTIONS_UNBUCKETED = "Unbucketed"
TRANSACTIONS_UNCATEGORISED = "Uncategorised"
TRANSACTIONS_TAB_SCHEMA = {
    "End of Month": pl.Date,
    "Budgeted": pl.Utf8,
    "Bucket": pl.Utf8,
    "Category": pl.Utf8,
    "Total": pl.Float64,
}

TABS_SCHEMA = {**ACCOUNTS_SCHEMA, **CLASSIFIER_SCHEMA, **BALANCES_SCHEMA, **TRANSACTIONS_YEAR_TAB_SCHEMA}
ERROR_CODES = {
    "TAB_UNUSABLE": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "ACCOUNT_DUPLICATE": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "ACCOUNT_FROM": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "ACCOUNT_MISSING": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "ACCOUNT_NAME": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "ACCOUNT_NAME_SHARED": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "ACCOUNT_STATUS": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "ACCOUNT_TYPE": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "ACCOUNT_UNMAPPED": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "REDBARK_GONE": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_BANK_CODE": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_BUCKET": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_BUDGETED": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_CATEGORY": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_CATEGORY_CASE": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_CODE_LIST": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_CODE_ROWS": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_MERCHANT_CODE": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_PATTERN": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_PATTERN_CONFLICT": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_UNBUCKETED": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_TIE": (plugin.LOG_KIND_WARNING, True, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_SHARE": (plugin.LOG_KIND_WARNING, True, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_HELD": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "CHANGES_UNLOGGED": (plugin.LOG_KIND_ERROR, False, plugin.CTR_SRC_SOURCES),
    "BALANCE_MANUAL_STALE": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_DATA),
    "TRANSACTION_KEY": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_SOURCES),
    "BALANCE_ABSENT": (plugin.LOG_KIND_WARNING, True, plugin.CTR_SRC_DATA),
    "REDBARK_ACCOUNTS": (plugin.LOG_KIND_INFO, True, plugin.CTR_SRC_SOURCES),
    "BALANCE_RESPONSE": (plugin.LOG_KIND_INFO, True, plugin.CTR_SRC_SOURCES),
    "BALANCE_STALE": (plugin.LOG_KIND_INFO, True, plugin.CTR_SRC_SOURCES),
    "TRANSACTION_CALL": (plugin.LOG_KIND_INFO, True, plugin.CTR_SRC_SOURCES),
    "TRANSACTION_RESPONSE": (plugin.LOG_KIND_INFO, True, plugin.CTR_SRC_SOURCES),
    "ACCOUNT_NOT_MANUAL": (plugin.LOG_KIND_ERROR, False, plugin.CTR_SRC_DATA),
    "FILE_UNREADABLE": (plugin.LOG_KIND_ERROR, False, plugin.CTR_SRC_DATA),
    "VALUE_UNPARSED": (plugin.LOG_KIND_ERROR, False, plugin.CTR_SRC_DATA),
    "BALANCE_DUPLICATE": (plugin.LOG_KIND_ERROR, False, plugin.CTR_SRC_DATA),
    "DATE_BEFORE_FROM": (plugin.LOG_KIND_ERROR, False, plugin.CTR_SRC_DATA),
    "DATE_FUTURE": (plugin.LOG_KIND_ERROR, False, plugin.CTR_SRC_DATA),
    "ACCOUNT_LINKED": (plugin.LOG_KIND_ERROR, False, plugin.CTR_SRC_DATA),
    "SPLIT_INVALID": (plugin.LOG_KIND_ERROR, False, plugin.CTR_SRC_DATA),
    "TRANSACTION_DECIMALS": (plugin.LOG_KIND_ERROR, False, plugin.CTR_SRC_DATA),
    "TRANSACTION_DESCRIPTION": (plugin.LOG_KIND_ERROR, False, plugin.CTR_SRC_DATA),
    "TRANSACTION_VETTED": (plugin.LOG_KIND_ERROR, False, plugin.CTR_SRC_DATA),
    "TRANSACTION_ZERO": (plugin.LOG_KIND_ERROR, False, plugin.CTR_SRC_DATA),
    "BALANCE_SIGN": (plugin.LOG_KIND_WARNING, False, plugin.CTR_SRC_DATA),
    "BALANCE_JUMP": (plugin.LOG_KIND_WARNING, False, plugin.CTR_SRC_DATA),
    "CATEGORY_UNKNOWN": (plugin.LOG_KIND_WARNING, False, plugin.CTR_SRC_DATA),
    "MANUAL_DUPLICATE": (plugin.LOG_KIND_WARNING, False, plugin.CTR_SRC_DATA),
    "TRANSACTION_GONE": (plugin.LOG_KIND_WARNING, False, plugin.CTR_SRC_DATA),
    "DEDUPE_REMOVED": (plugin.LOG_KIND_INFO, False, plugin.CTR_SRC_DATA),
    "TRANSACTIONS_UNCLASSIFIED": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_DATA),
    "TRANSACTIONS_UNCLASSIFIED_CURRENT": (plugin.LOG_KIND_WARNING, True, plugin.CTR_SRC_DATA),
    "TRANSACTIONS_UNVETTED": (plugin.LOG_KIND_ERROR, True, plugin.CTR_SRC_DATA),
    "TRANSACTIONS_UNVETTED_CURRENT": (plugin.LOG_KIND_WARNING, True, plugin.CTR_SRC_DATA),
    "TRANSACTION_TWO_ACCOUNTS": (plugin.LOG_KIND_WARNING, True, plugin.CTR_SRC_DATA),
    "TRANSACTIONS_MOVED": (plugin.LOG_KIND_WARNING, False, plugin.CTR_SRC_DATA),
}
CLASSIFIER_HOLDING_CODES = {
    "CLASSIFIER_BANK_CODE",
    "CLASSIFIER_CATEGORY",
    "CLASSIFIER_CATEGORY_CASE",
    "CLASSIFIER_CODE_LIST",
    "CLASSIFIER_CODE_ROWS",
    "CLASSIFIER_MERCHANT_CODE",
    "CLASSIFIER_PATTERN",
    "CLASSIFIER_PATTERN_CONFLICT",
    "CLASSIFIER_SHARE",
    "CLASSIFIER_TIE",
}

CHANGES_FILE_PREFIX = "bank_reclassified"
CHANGES_SCHEMA = {
    "Run": pl.Utf8,
    "Source": pl.Utf8,
    "Year File": pl.Utf8,
    "Transaction ID": pl.Utf8,
    "Part": pl.Int64,
    "Date": pl.Date,
    "Account": pl.Utf8,
    "Amount": pl.Float64,
    "Description": pl.Utf8,
    "Manual Before": pl.Utf8,
    "Manual After": pl.Utf8,
    "Derived Before": pl.Utf8,
    "Derived After": pl.Utf8,
    "Vetted Before": pl.Utf8,
    "Vetted After": pl.Utf8,
    "File MD5": pl.Utf8,
}
CHANGES_SOURCE_SHEET = "sheet"
CHANGES_SOURCE_CLASSIFIER = "classifier"

REPOS_BANK = plugin.Repos(
    preview={
        "drive_folder": "1ELcrbuJxjlYcDJ8FRWacvsKvSM5sypaV",
        "sheet_key": "1l69phyvfkK65WKnoShNgIIMkk8S6E_ZEI3M7Pep0eqg",
    },
    release={
        "drive_folder": "1bfBMTDUj2Y5sZSu0yMR48ao_b6XEI72r",
        "sheet_key": "1Q5kdvUuzYoJIgT8UAlF1PhStrjAJ66P8ihb_MkJFT98",
    },
)


class Bank(plugin.Plugin):
    def _run(self):
        now = self.now()
        today = now.date()
        month_start = today.replace(day=1)
        previous_month_start = (month_start - timedelta(days=1)).replace(day=1)
        sheet_key = self.remote_repos.sheet_key
        bank_files: dict[str, plugin.DownloadResult] = {}
        files_changed: dict[str, str] = {}
        files_read: dict[tuple[str, tuple], pl.DataFrame] = {}
        files_unreadable: set[str] = set()
        errors: list[dict] = []

        # Identify Accounts
        def _bank_account_ids(_accounts_df: pl.DataFrame) -> pl.DataFrame:
            return _accounts_df.with_columns(
                pl.Series("Account ID", [bank_record_id(ACCOUNT_ID_NAMESPACE, *_key) for _key in _accounts_df.select(["Institution", "Number"]).iter_rows()], dtype=pl.Utf8)
            )

        # Apply Accounts
        def _bank_accounts_applied(_facts_df: pl.DataFrame, _accounts_df: pl.DataFrame) -> pl.DataFrame:
            _columns = ["Account Institution", "Account Number", "Account Type"]
            _facts_df = _facts_df.drop(_columns, strict=False)
            if len(_accounts_df) == 0 or len(_facts_df) == 0:
                return _facts_df.with_columns([pl.lit(None, dtype=pl.Utf8).alias(_column) for _column in _columns])
            _accounts_current_df = (
                _accounts_df.sort("From")
                .group_by("Account ID", maintain_order=True)
                .agg(
                    pl.col("Institution").last().alias("Account Institution"),
                    pl.col("Number").last().alias("Account Number"),
                    pl.col("Type").first().alias("__type_first"),
                )
            )
            return (
                _facts_df.with_row_index("__row")
                .sort("Date")
                .join_asof(
                    _accounts_df.select([pl.col("From"), pl.col("Account ID"), pl.col("Name").alias("__name"), pl.col("Type").alias("__type")]).sort("From"),
                    left_on="Date",
                    right_on="From",
                    by="Account ID",
                    strategy="backward",
                    check_sortedness=False,
                )
                .join(_accounts_current_df, on="Account ID", how="left")
                .with_columns(pl.coalesce("__name", "Account").alias("Account"), pl.coalesce("__type", "__type_first").alias("Account Type"))
                .sort("__row")
                .drop(["__row", "From", "__name", "__type", "__type_first"])
            )

        # Carry Balances
        def _bank_balances_carried(_balances_df: pl.DataFrame) -> pl.DataFrame:
            _manual_ids = _bank_accounts_current().filter(pl.col("Status") == ACCOUNT_STATUS_MANUAL)["Account ID"]
            _at = pl.col("Date").dt.combine(pl.col("Time").str.zfill(8).str.to_time("%H:%M:%S", strict=False))
            _manual_df = (
                _balances_df.filter(pl.col("Balance Manual").is_not_null() & pl.col("Account ID").is_in(_manual_ids.implode()))
                .select(["Account ID", "Account", "Balance Manual", _at.alias("__at")])
                .drop_nulls("__at")
                .sort("__at")
            )
            _moments_df = _balances_df.filter(pl.col("Balance Linked").is_not_null()).select(["Date", pl.col("Time").str.zfill(8)]).unique()
            if len(_manual_df) == 0 or len(_moments_df) == 0:
                return _balances_df.clear().select(list(BALANCES_SCHEMA))
            return (
                _moments_df.join(_manual_df.select("Account ID").unique(), how="cross")
                .with_columns(_at.alias("__at"))
                .sort("__at")
                .join_asof(_manual_df, on="__at", by="Account ID", strategy="backward", check_sortedness=False)
                .filter(pl.col("Balance Manual").is_not_null())
                .join(_balances_df.filter(pl.col("Balance Manual").is_not_null()).select(["Date", pl.col("Time").str.zfill(8), "Account ID"]), on=["Date", "Time", "Account ID"], how="anti")
                .select(
                    [
                        pl.col("Date"),
                        pl.col("Time"),
                        pl.col("Account"),
                        pl.col("Balance Manual").alias("Balance"),
                        pl.col("Balance Manual"),
                        pl.lit(None, dtype=pl.Float64).alias("Balance Linked"),
                        pl.col("Account ID"),
                        pl.lit(None, dtype=pl.Utf8).alias("Balance ID"),
                    ]
                )
                .sort(["Date", "Time", "Account ID"])
            )

        # Queue File
        def _bank_changed(_path, _reason):
            if _path not in files_changed:
                files_changed[_path] = _reason
                self.print_log(f"File [{basename(_path)}] queued for reprocessing as [{_reason}]", level="debug")

        # Parse File
        def _bank_file(_path) -> tuple[str, int]:
            _match = cast(re.Match, re.fullmatch(FILE_NAME_PATTERN, basename(_path).lower()))
            return f"{_match[1]}_{_match[2]}", int(_match[3])

        # List Files
        def _bank_paths(*_prefixes):
            return [
                _path
                for _prefix in _prefixes
                for _path in sorted(abspath(_path).lower() for _path in glob.glob(f"{self.local_cache}/{_prefix}_*.csv") if re.fullmatch(FILE_NAME_PATTERN, basename(_path).lower()))
            ]

        # Name File
        def _bank_path(_family, _year):
            return abspath(f"{self.local_cache}/{_family}_{_year}.csv").lower()

        # Read File
        def _bank_read(_path: str, _schema: dict) -> pl.DataFrame:
            _key = (_path, tuple(_schema))
            if _key not in files_read:
                _data_df = self.csv_read(_path, schema=_schema, print_rows=0)
                files_read[_key] = _data_df.with_columns([pl.lit(None, dtype=_dtype).alias(_column) for _column, _dtype in _schema.items() if _column not in _data_df.columns]).select(
                    [pl.col(_column).cast(_dtype) for _column, _dtype in _schema.items()]
                )
            return files_read[_key]

        # Read File Safely
        def _bank_readable(_path: str, _schema: dict) -> pl.DataFrame | None:
            if _path in files_unreadable:
                return None
            try:
                return _bank_read(_path, _schema)
            except Exception as _exception:
                files_unreadable.add(_path)
                self.print_log(f"File [{basename(_path)}] unreadable, kept and skipped", exception=_exception)
                return None

        # Check File Writable
        def _bank_writable(_path: str) -> bool:
            return not isfile(_path) or _bank_readable(_path, TRANSACTIONS_SCHEMA) is not None

        # Write File
        def _bank_write(_data_df: pl.DataFrame, _path: str, _reason: str):
            for _key in [_key for _key in files_read if _key[0] == _path]:
                del files_read[_key]
            _balances = _bank_file(_path)[0].endswith("_balances")
            if len(_data_df) == 0:
                if isfile(_path):
                    self.csv_write(pl.DataFrame(schema=BALANCES_SCHEMA if _balances else TRANSACTIONS_SCHEMA), _path, print_verb="emptied", print_rows=0)
                    _bank_changed(_path, _reason)
                return
            if _balances:
                _data_df = bank_balances_identified(_data_df.select(list(BALANCES_SCHEMA))).sort(["Date", "Time", "Account ID"], descending=[True, True, False], maintain_order=True)
            else:
                _data_df = (
                    bank_transactions_identified(_data_df.select(list(TRANSACTIONS_SCHEMA)))
                    .drop("Split")
                    .with_columns(pl.col("Merchant Code").cast(pl.Utf8), bank_flag("Vetted").alias("Vetted"))
                    .sort(["Date", "Account ID", "Amount", "Description"], descending=[True, False, False, False], maintain_order=True, nulls_last=True)
                )
            os.makedirs(dirname(_path), exist_ok=True)
            self.csv_write(_data_df, _path, print_verb="written", print_rows=0)
            _bank_changed(_path, _reason)

        # Name Year Files
        def _bank_year_paths(_year):
            return [_bank_path("manual_transactions", _year), _bank_path("redbark_transactions", _year)]

        # Read Tab
        def _bank_raw(_path: str | None) -> pl.DataFrame | None:
            return pl.read_csv(_path, infer_schema=False, raise_if_empty=False) if _path and isfile(_path) else None

        # Clean Text
        def _bank_text(_column):
            return pl.col(_column).str.strip_chars().replace("", None)

        # Normalise Name
        def _bank_name(_column):
            return pl.col(_column).str.strip_chars().str.to_lowercase().str.replace_all(r"\s+", " ")

        # Letter Column
        def _bank_letter(_columns, _column):
            return chr(ord("A") + _columns.index(_column))

        # Raise Error
        def _bank_error(_tab, _key, _code, _detail):
            self.error(errors, _tab, _key, _code, _detail)

        # Download Drive Data
        drive_errored = self.get_counter(plugin.CTR_SRC_SOURCES, plugin.CTR_ACT_ERRORED)
        if not plugin.config.disable_drive_downloads:
            for file_name, (file_present, file_downloaded) in self.drive_synchronise(self.remote_repos.drive_folder, self.local_cache, download=True).items():
                file_path = abspath(join(self.local_cache, basename(str(file_name)))).lower()
                if file_present and re.fullmatch(FILE_NAME_PATTERN, basename(file_path)):
                    bank_files[file_path] = plugin.DownloadResult(plugin.DownloadStatus.DOWNLOADED if file_downloaded else plugin.DownloadStatus.CACHED, [file_path])
        drive_failed = self.get_counter(plugin.CTR_SRC_SOURCES, plugin.CTR_ACT_ERRORED) > drive_errored

        # Download Sheet Data
        started_time = time.time()
        sheet_years = sorted({_bank_file(path)[1] for path in _bank_paths("redbark_transactions", "manual_transactions")} | {today.year})
        sheet_tabs = ["Accounts", "Classifier", "Balances", *(f"Transactions_{year}" for year in sheet_years)]
        sheet_result = self.sheet_download(sheet_key, "Bank", sheet_tabs, schema=TABS_SCHEMA)
        sheet_files: dict[str, str] = dict(zip(sheet_tabs, sheet_result.file_paths, strict=True)) if sheet_result.file_status != plugin.DownloadStatus.FAILED else {}
        sheet_downloaded = sheet_result.file_status == plugin.DownloadStatus.DOWNLOADED
        self.print_log(f"Sheet tabs [{len(sheet_tabs)}] status [{sheet_result.file_status.name}]", started=started_time)

        # Build Classifier Matchers
        def _bank_matchers(_rows_df: pl.DataFrame, _report: bool) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
            _pattern_rows_df = _rows_df.filter(pl.col("Pattern").is_not_null())
            if _report:
                for _row in _pattern_rows_df.filter(pl.col("Bank Code").str.contains(",") | pl.col("Merchant Code").str.contains(",")).iter_rows(named=True):
                    _bank_error("Classifier", f"row {_row['Row']}", "CLASSIFIER_CODE_LIST", "code list on a pattern row")
                for _row in _pattern_rows_df.filter(pl.col("Pattern").str.len_chars() < CLASSIFIER_PATTERN_MIN).iter_rows(named=True):
                    _bank_error("Classifier", f"row {_row['Row']}", "CLASSIFIER_PATTERN", f"pattern [{_row['Pattern']}] under [{CLASSIFIER_PATTERN_MIN}] characters")
            _patterns_df = (
                _pattern_rows_df.filter(pl.col("Pattern").str.len_chars() >= CLASSIFIER_PATTERN_MIN).select([_bank_name("Pattern").alias("__pattern"), "Category"]).unique(maintain_order=True)
            )
            if _report:
                for _pattern, _categories in _patterns_df.group_by("__pattern", maintain_order=True).agg(pl.col("Category")).filter(pl.col("Category").list.len() > 1).iter_rows():
                    _bank_error("Classifier", _pattern, "CLASSIFIER_PATTERN_CONFLICT", f"pattern in categories [{', '.join(_categories)}] applied to neither")
            _codes_df = _rows_df.select(["Category", pl.col("Bank Code").str.split(","), pl.col("Merchant Code").str.split(",")])
            _codes: dict[str, pl.DataFrame] = {}
            for _column, _valid, _code_name, _label, _invalid in (
                ("Bank Code", pl.col("Bank Code").is_in(CLASSIFIER_BANK_CODES), "CLASSIFIER_BANK_CODE", "bank code", "not a CDR code"),
                (
                    "Merchant Code",
                    pl.col("Merchant Code").str.contains(r"^\d{4}$") & (pl.col("Merchant Code") != CLASSIFIER_MERCHANT_CODE_NONE),
                    "CLASSIFIER_MERCHANT_CODE",
                    "merchant code",
                    "not four digits",
                ),
            ):
                _column_df = _codes_df.explode(_column).select([pl.col(_column).str.strip_chars(), "Category"]).filter(pl.col(_column).str.len_chars() > 0).unique(maintain_order=True)
                if _report:
                    for _code in _column_df.filter(~_valid)[_column].to_list():
                        _bank_error("Classifier", _code, _code_name, f"{_label} {_invalid}")
                _column_df = _column_df.filter(_valid)
                if _report:
                    for _code, _categories in _column_df.group_by(_column, maintain_order=True).agg(pl.col("Category")).filter(pl.col("Category").list.len() > 1).iter_rows():
                        _bank_error("Classifier", _code, _code_name, f"{_label} in categories [{', '.join(_categories)}] applied to neither")
                _codes[_column] = _column_df.filter(pl.col(_column).is_unique())
            return (
                _patterns_df.filter(pl.col("__pattern").is_unique()),
                _codes["Bank Code"].rename({"Category": "__bank"}),
                _codes["Merchant Code"].rename({"Category": "__merchant"}),
            )

        # Load Classifier Data
        started_time = time.time()
        classifier_df = pl.DataFrame(schema=CLASSIFIER_SCHEMA)
        classifier_raw_df = _bank_raw(sheet_files.get("Classifier"))
        classifier_snapshot_file = abspath(f"{self.local_cache}/__bank_classifier.csv")
        classifier_snapshot_df = _bank_read(classifier_snapshot_file, CLASSIFIER_SCHEMA) if isfile(classifier_snapshot_file) else None
        classifier_patterns_df = pl.DataFrame(schema={"__pattern": pl.Utf8, "Category": pl.Utf8})
        classifier_bank_df = pl.DataFrame(schema={"Bank Code": pl.Utf8, "__bank": pl.Utf8})
        classifier_merchant_df = pl.DataFrame(schema={"Merchant Code": pl.Utf8, "__merchant": pl.Utf8})
        classifier_errors_start = len(errors)
        if classifier_raw_df is not None:
            try:
                if list(classifier_raw_df.columns[: len(CLASSIFIER_SCHEMA)]) != list(CLASSIFIER_SCHEMA):
                    raise ValueError(f"classifier columns [{', '.join(classifier_raw_df.columns)}] not [{', '.join(CLASSIFIER_SCHEMA)}]")
                if classifier_raw_df.height == 0:
                    raise ValueError("classifier has no rows")
                classifier_rows_df = (
                    classifier_raw_df.with_row_index("Row", offset=2)
                    .with_columns([_bank_text(column).alias(column) for column in CLASSIFIER_SCHEMA])
                    .filter(~pl.all_horizontal([pl.col(column).is_null() for column in CLASSIFIER_SCHEMA]))
                )
                for row in classifier_rows_df.filter(pl.col("Category").is_null()).iter_rows(named=True):
                    _bank_error("Classifier", f"row {row['Row']}", "CLASSIFIER_CATEGORY", "category blank")
                classifier_rows_df = classifier_rows_df.drop_nulls("Category")
                category_buckets_df = classifier_rows_df.group_by("Category", maintain_order=True).agg(pl.col("Bucket").drop_nulls().unique().sort())
                for category, buckets in category_buckets_df.filter(pl.col("Bucket").list.len() != 1).iter_rows():
                    _bank_error("Classifier", category, "CLASSIFIER_BUCKET", f"buckets [{', '.join(buckets)}] left unbucketed")
                category_bucket_df = category_buckets_df.with_columns(pl.when(pl.col("Bucket").list.len() == 1).then(pl.col("Bucket").list.first()).alias("Bucket"))
                bucket_budgeted_df = (
                    classifier_rows_df.join(category_bucket_df.rename({"Bucket": "__bucket"}), on="Category")
                    .drop_nulls("__bucket")
                    .group_by("__bucket", maintain_order=True)
                    .agg(pl.coalesce(bank_flag("Budgeted"), pl.col("Budgeted")).unique())
                )
                for bucket, budgeted in bucket_budgeted_df.iter_rows():
                    if len(budgeted) != 1 or budgeted[0] not in FLAGS:
                        _bank_error("Classifier", bucket, "CLASSIFIER_BUDGETED", f"budgeted [{', '.join(str(value) for value in budgeted)}] not one of [{', '.join(FLAGS)}] counted as [{FLAG_NO}]")
                bucket_budgeted_df = bucket_budgeted_df.select(
                    [
                        pl.col("__bucket").alias("Bucket"),
                        pl.when((pl.col("Budgeted").list.len() == 1) & (pl.col("Budgeted").list.first() == FLAG_YES)).then(pl.lit(FLAG_YES)).otherwise(pl.lit(FLAG_NO)).alias("Budgeted"),
                    ]
                )
                for name, categories in (
                    classifier_rows_df.select(["Category"])
                    .unique(maintain_order=True)
                    .group_by(_bank_name("Category").alias("__name"))
                    .agg(pl.col("Category"))
                    .filter(pl.col("Category").list.len() > 1)
                    .iter_rows()
                ):
                    _bank_error("Classifier", name, "CLASSIFIER_CATEGORY_CASE", f"categories [{', '.join(categories)}] differ only in case or spacing")
                for category, count in classifier_rows_df.filter(pl.col("Pattern").is_null()).group_by("Category").len().filter(pl.col("len") > 1).iter_rows():
                    _bank_error("Classifier", category, "CLASSIFIER_CODE_ROWS", f"code rows [{count}] for one category")
                for row in classifier_raw_df.with_row_index("Row", offset=2).filter(pl.col("Pattern").is_not_null() & (pl.col("Pattern") != pl.col("Pattern").str.strip_chars())).iter_rows(named=True):
                    _bank_error("Classifier", f"row {row['Row']}", "CLASSIFIER_PATTERN", f"pattern [{row['Pattern']}] has edge spaces")
                classifier_patterns_df, classifier_bank_df, classifier_merchant_df = _bank_matchers(classifier_rows_df, True)
                classifier_df = (
                    classifier_rows_df.drop(["Row", "Bucket", "Budgeted"])
                    .join(category_bucket_df, on="Category", how="left", maintain_order="left")
                    .join(bucket_budgeted_df, on="Bucket", how="left", maintain_order="left")
                    .select(list(CLASSIFIER_SCHEMA))
                )
            except Exception as exception:
                _bank_error("Classifier", "tab", "TAB_UNUSABLE", f"tab unusable [{exception}]")
        classifier_usable = len(classifier_df) > 0
        classifier_content_changed = classifier_usable and (classifier_snapshot_df is None or not classifier_snapshot_df.equals(classifier_df))
        classifier_holding = classifier_content_changed and any(error["Code"] in CLASSIFIER_HOLDING_CODES for error in errors[classifier_errors_start:])
        classifier_buckets = ["Category", "Bucket", "Budgeted"]
        classifier_buckets_df = classifier_df.select(classifier_buckets).unique(maintain_order=True)
        classifier_changed = classifier_usable and (classifier_snapshot_df is None or not classifier_snapshot_df.select(classifier_buckets).unique(maintain_order=True).equals(classifier_buckets_df))
        classifier_categories = set(classifier_df["Category"].to_list())
        self.print_log(
            f"Classifier tab [{len(classifier_df)}] rows, patterns [{len(classifier_patterns_df)}] bank codes [{len(classifier_bank_df)}] "
            f"merchant codes [{len(classifier_merchant_df)}], changed [{classifier_content_changed}] buckets changed [{classifier_changed}]",
            started=started_time,
        )

        # Load Account Data
        started_time = time.time()
        accounts_df = pl.DataFrame(schema={**ACCOUNTS_SCHEMA, "Row": pl.Int64, "Account ID": pl.Utf8})
        accounts_raw_df = _bank_raw(sheet_files.get("Accounts"))
        accounts_snapshot_file = abspath(f"{self.local_cache}/__bank_accounts_dimension.csv")
        accounts_snapshot_df = _bank_read(accounts_snapshot_file, ACCOUNTS_SCHEMA) if isfile(accounts_snapshot_file) else None
        accounts_empty = accounts_raw_df is not None and accounts_raw_df.height == 0 and all(column in accounts_raw_df.columns for column in ("Institution", "Number"))
        if accounts_raw_df is not None and not accounts_empty:
            try:
                if accounts_raw_df.height == 0:
                    raise ValueError("accounts have no members")
                accounts_missing = [column for column in ("Institution", "Number") if column not in accounts_raw_df.columns]
                if accounts_missing:
                    raise ValueError(f"accounts missing natural key columns [{', '.join(accounts_missing)}]")
                accounts_parsed_df = (
                    accounts_raw_df.with_row_index("Row", offset=2)
                    .with_columns(pl.col("Row").cast(pl.Int64))
                    .with_columns([pl.lit(None, dtype=pl.Utf8).alias(column) for column in ACCOUNTS_SCHEMA if column not in accounts_raw_df.columns])
                    .with_columns([_bank_text(column).alias(column) for column in ACCOUNTS_SCHEMA])
                    .with_columns(pl.col("From").str.to_date("%Y-%m-%d", strict=False).alias("__from"))
                )
                accounts_unparsed = accounts_parsed_df.filter(pl.col("From").is_not_null() & pl.col("__from").is_null())["From"].to_list()
                if accounts_unparsed:
                    raise ValueError(f"accounts unparseable from dates [{', '.join(accounts_unparsed)}]")
                accounts_parsed_df = accounts_parsed_df.with_columns(pl.col("__from").fill_null(date(1, 1, 1)).alias("From")).drop_nulls(["Institution", "Number"]).select(["Row", *ACCOUNTS_SCHEMA])
                if accounts_parsed_df.height == 0:
                    raise ValueError("accounts have no members")
                accounts_duplicated = accounts_parsed_df.filter(pl.struct(["Institution", "Number", "From"]).is_duplicated())
                if len(accounts_duplicated):
                    raise ValueError(f"accounts duplicate rows [{', '.join(sorted({f'{row[0]} {row[1]} {row[2]}' for row in accounts_duplicated.select(['Institution', 'Number', 'From']).rows()}))}]")
                for row in accounts_parsed_df.filter(pl.col("Type").is_not_null() & ~pl.col("Type").is_in(ACCOUNT_TYPES)).iter_rows(named=True):
                    _bank_error("Accounts", f"row {row['Row']}", "ACCOUNT_TYPE", f"type [{row['Type']}] read as [{ACCOUNT_TYPE_ASSET}]")
                for row in accounts_parsed_df.filter(pl.col("Name").is_null()).iter_rows(named=True):
                    _bank_error("Accounts", f"row {row['Row']}", "ACCOUNT_NAME", "name blank")
                for row in accounts_parsed_df.filter(pl.col("From") > today).iter_rows(named=True):
                    _bank_error("Accounts", f"row {row['Row']}", "ACCOUNT_FROM", f"from [{row['From']}] in the future")
                for row in accounts_parsed_df.filter(pl.col("Status").is_not_null() & ~pl.col("Status").is_in(ACCOUNT_STATUSES)).iter_rows(named=True):
                    _bank_error("Accounts", f"row {row['Row']}", "ACCOUNT_STATUS", f"status [{row['Status']}] not one of [{', '.join(ACCOUNT_STATUSES)}]")
                accounts_df = _bank_account_ids(accounts_parsed_df.with_columns(pl.when(pl.col("Type").is_in(ACCOUNT_TYPES)).then(pl.col("Type")).otherwise(pl.lit(ACCOUNT_TYPE_ASSET)).alias("Type")))
            except Exception as exception:
                _bank_error("Accounts", "tab", "TAB_UNUSABLE", f"tab unusable [{exception}]")
        accounts_usable = len(accounts_df) > 0

        def _bank_accounts_current() -> pl.DataFrame:
            return (
                accounts_df.sort("From")
                .group_by("Account ID", maintain_order=True)
                .agg(
                    pl.col("Institution").last(),
                    pl.col("Number").last(),
                    pl.col("Name").last(),
                    pl.col("Status").last(),
                    pl.col("Type").last(),
                    pl.col("Redbark Account ID").last(),
                    pl.col("Redbark Connection ID").last(),
                    pl.col("From").min().alias("From First"),
                )
            )

        def _bank_accounts_resolved(_names_df: pl.DataFrame) -> pl.DataFrame:
            _manual_df = _bank_accounts_current().filter(pl.col("Status") == ACCOUNT_STATUS_MANUAL).select("Account ID")
            _versions_df = accounts_df.join(_manual_df, on="Account ID").select(["Account ID", "From", _bank_name("Name").alias("__version_name")]).sort("From")
            _names_df = _names_df.with_row_index("__resolve")
            _candidates_df = (
                _names_df.select(["__resolve", "__on", "__name"])
                .join(_manual_df, how="cross")
                .drop_nulls("__on")
                .sort("__on")
                .join_asof(_versions_df, left_on="__on", right_on="From", by="Account ID", strategy="backward", check_sortedness=False)
                .join(_versions_df.group_by("Account ID").agg(pl.col("__version_name").first().alias("__first_name")), on="Account ID", how="left")
                .filter(pl.coalesce("__version_name", "__first_name") == pl.col("__name"))
                .group_by("__resolve")
                .agg(pl.col("Account ID").unique().alias("__ids"))
            )
            return (
                _names_df.join(_candidates_df, on="__resolve", how="left", maintain_order="left")
                .with_columns(pl.when(pl.col("__ids").list.len() == 1).then(pl.col("__ids").list.first()).otherwise(None).alias("__account_id"))
                .drop(["__resolve", "__ids"])
            )

        # Download Account Data
        redbark_accounts: list[dict] | None = None
        redbark_accounts_file = abspath(f"{self.local_cache}/_redbark_accounts.csv")

        def _bank_accounts_fetched(_reason) -> list[dict]:
            nonlocal redbark_accounts
            if redbark_accounts is None:
                try:
                    _result = self.redbark_download(["/v1/accounts"], redbark_accounts_file, REDBARK_ACCOUNTS_COLUMNS, ignore=True)
                    _accounts_df = _result.data_frame
                    if _accounts_df is None:
                        raise ValueError(_result.errors[0]["Detail"] if _result.errors else "accounts download failed")
                    _accounts = _accounts_df.to_dicts()
                    if len(_accounts) == 0:
                        raise ValueError("accounts response empty")
                    self.print_log(f"Accounts call [due] reason [{_reason}] returned [{len(_accounts)}] accounts", level="debug")
                    redbark_accounts = _accounts
                except Exception as _exception:
                    redbark_accounts = []
                    _bank_error("Redbark", "accounts", "REDBARK_ACCOUNTS", f"accounts call failed [{_exception}]")
            return redbark_accounts or []

        def _bank_redbark_key(_institution, _number):
            return str(_institution or "").strip(), str(_number or "").strip()

        accounts_writes: list[tuple[int, dict]] = []
        accounts_appends: list[dict] = []

        def _bank_accounts_filled(_rows_mask, _replace):
            nonlocal accounts_df
            _by_key: dict[tuple[str, str], list[dict]] = {}
            for _account in redbark_accounts or []:
                _by_key.setdefault(_bank_redbark_key(_account.get("institutionName"), _account.get("accountNumber")), []).append(_account)
            _updates = []
            for _row in accounts_df.filter(_rows_mask).iter_rows(named=True):
                _matches = _by_key.get(_bank_redbark_key(_row["Institution"], _row["Number"]), [])
                if len(_matches) == 1:
                    _cells = {"Status": ACCOUNT_STATUS_LINKED, "Redbark Account ID": str(_matches[0].get("id")), "Redbark Connection ID": str(_matches[0].get("connectionId"))}
                elif len(_matches) > 1:
                    _cells = {"Status": ACCOUNT_STATUS_DUPLICATE, "Redbark Account ID": None, "Redbark Connection ID": None}
                elif _replace:
                    continue
                else:
                    _cells = {"Status": ACCOUNT_STATUS_MISSING, "Redbark Account ID": None, "Redbark Connection ID": None}
                if any(_row[_column] != _value for _column, _value in _cells.items()):
                    _updates.append((_row["Row"], _cells))
            for _row_number, _cells in _updates:
                accounts_writes.append((_row_number, _cells))
                accounts_df = accounts_df.with_columns(
                    [pl.when(pl.col("Row") == _row_number).then(pl.lit(_value, dtype=pl.Utf8)).otherwise(pl.col(_column)).alias(_column) for _column, _value in _cells.items()]
                )
            if not _replace:
                _keys = {_bank_redbark_key(_row["Institution"], _row["Number"]) for _row in accounts_df.iter_rows(named=True)}
                for _key, _matches in _by_key.items():
                    if _key not in _keys and len(_matches) == 1 and all(_key):
                        _type = ACCOUNT_TYPE_LIABILITY if str(_matches[0].get("type") or "") == REDBARK_TYPE_CREDIT else ACCOUNT_TYPE_ASSET
                        _appended = {
                            "From": None,
                            "Institution": _key[0],
                            "Number": _key[1],
                            "Name": str(_matches[0].get("name") or ""),
                            "Type": _type,
                            "Status": ACCOUNT_STATUS_LINKED,
                            "Redbark Account ID": str(_matches[0].get("id")),
                            "Redbark Connection ID": str(_matches[0].get("connectionId")),
                            "Account ID": bank_record_id(ACCOUNT_ID_NAMESPACE, *_key),
                        }
                        accounts_appends.append(_appended)
                        self.print_log(f"Accounts row appended for Redbark account [{_appended['Name']}] id [{_appended['Redbark Account ID']}]")
                        _row = {**_appended, "From": date(1, 1, 1), "Row": (0 if accounts_raw_df is None else len(accounts_raw_df)) + 1 + len(accounts_appends)}
                        accounts_df = pl.concat([accounts_df, pl.DataFrame([_row], schema=accounts_df.schema)])

        if accounts_empty and not plugin.config.disable_source_downloads and _bank_accounts_fetched("empty tab"):
            _bank_accounts_filled(pl.lit(False), False)
        accounts_usable = len(accounts_df) > 0
        if accounts_empty and not accounts_usable:
            _bank_error("Accounts", "tab", "TAB_UNUSABLE", "tab unusable [accounts have no members]")
        accounts_call_reason = None
        if not plugin.config.disable_source_downloads and accounts_usable and not accounts_empty:
            accounts_blank_mask = pl.col("Status").is_null() | ((pl.col("Status") == ACCOUNT_STATUS_LINKED) & (pl.col("Redbark Account ID").is_null() | pl.col("Redbark Connection ID").is_null()))
            accounts_differs = accounts_snapshot_df is None or not accounts_snapshot_df.equals(accounts_df.select(list(ACCOUNTS_SCHEMA)))
            accounts_age_days = (now.timestamp() - getmtime(redbark_accounts_file)) / 86400 if isfile(redbark_accounts_file) else None
            if accounts_differs and len(accounts_df.filter(accounts_blank_mask)) > 0:
                accounts_call_reason = "tab edit"
            elif accounts_age_days is None or accounts_age_days >= ACCOUNTS_CHECK_DAYS:
                accounts_call_reason = "weekly"
            if accounts_call_reason is not None and _bank_accounts_fetched(accounts_call_reason):
                _bank_accounts_filled(pl.col("Status").is_null() | pl.col("Status").is_in([ACCOUNT_STATUS_LINKED, ACCOUNT_STATUS_MISSING, ACCOUNT_STATUS_DUPLICATE]), False)
        self.print_log(
            f"Accounts tab [{len(accounts_df)}] rows, [{len(accounts_df.filter(pl.col('Status') == ACCOUNT_STATUS_LINKED))}] linked "
            f"[{len(accounts_df.filter(pl.col('Status') == ACCOUNT_STATUS_MANUAL))}] manual [{len(accounts_df.filter(pl.col('Status') == ACCOUNT_STATUS_CLOSED))}] closed, "
            f"call [{'skipped' if accounts_call_reason is None else f'due] reason [{accounts_call_reason}'}]",
            started=started_time,
        )
        for row in accounts_df.filter(pl.col("Status") == ACCOUNT_STATUS_MISSING).iter_rows(named=True):
            _bank_error("Accounts", f"{row['Name']}", "ACCOUNT_MISSING", "account not on Redbark, make it Manual or Closed")
        for row in accounts_df.filter(pl.col("Status") == ACCOUNT_STATUS_DUPLICATE).iter_rows(named=True):
            _bank_error("Accounts", f"{row['Name']}", "ACCOUNT_DUPLICATE", "two Redbark accounts on one key")

        # Merge Sheet Balance Data
        started_time = time.time()
        merged_counts = {"balances": 0, "transactions": 0}
        merged_errors = len(errors)

        def _bank_balances_merged():
            _balances_raw_df = _bank_raw(sheet_files.get("Balances")) if sheet_downloaded else None
            if _balances_raw_df is not None and len(_balances_raw_df) > 0 and accounts_usable:
                _balances_missing = [_column for _column in ("Date", "Time", "Account", "Balance Manual", "Balance ID") if _column not in _balances_raw_df.columns]
                if _balances_missing:
                    _bank_error("Balances", "tab", "TAB_UNUSABLE", f"columns missing [{', '.join(_balances_missing)}]")
                else:
                    _balances_held_frames = [
                        _data_df.with_columns(pl.lit(_path).alias("__path"))
                        for _path in _bank_paths("redbark_balances", "manual_balances")
                        if (_data_df := _bank_readable(_path, BALANCES_SCHEMA)) is not None
                    ]
                    _balances_all_df = bank_balances_identified(pl.concat([pl.DataFrame(schema={**BALANCES_SCHEMA, "__path": pl.Utf8}), *_balances_held_frames], how="vertical_relaxed"))
                    _accounts_current_df = _bank_accounts_current()
                    _balances_baseline_df = (
                        pl.concat(
                            [
                                _balances_all_df.with_columns(pl.lit(False).alias("__carried")),
                                bank_balances_identified(_bank_balances_carried(_balances_all_df.drop("__path"))).with_columns(
                                    pl.lit(None, dtype=pl.Utf8).alias("__path"), pl.lit(True).alias("__carried")
                                ),
                            ],
                            how="diagonal_relaxed",
                        )
                        .join(_accounts_current_df.select(["Account ID", pl.col("Status").alias("__status"), pl.col("From First")]), on="Account ID", how="left", maintain_order="left")
                        .unique("Balance ID", keep="first", maintain_order=True)
                    )
                    _balances_rows_df = (
                        _balances_raw_df.with_row_index("__tab", offset=2)
                        .with_columns([_bank_text(_column).alias(_column) for _column in ("Date", "Time", "Account", "Balance Manual", "Balance ID")])
                        .with_columns(
                            pl.col("Date").str.to_date("%Y-%m-%d", strict=False).alias("__date"),
                            pl.col("Time").str.zfill(8).str.to_time("%H:%M:%S", strict=False).alias("__time"),
                            pl.col("Balance Manual").cast(pl.Float64, strict=False).alias("__value"),
                        )
                    )
                    _balances_candidates = []
                    _balances_deleted = []

                    _manual_edited = (
                        (pl.col("Balance Manual").is_null() != pl.col("Balance Manual_base").is_null())
                        | (pl.col("__value").is_null() & pl.col("Balance Manual").is_not_null())
                        | ((pl.col("__value") * 100).round() != (pl.col("Balance Manual_base") * 100).round()).fill_null(False)
                    )
                    _balances_edited_df = _balances_rows_df.filter(pl.col("Balance ID").is_not_null()).join(_balances_baseline_df, on="Balance ID", how="inner", suffix="_base").filter(_manual_edited)
                    for _row in _balances_edited_df.iter_rows(named=True):
                        if _row["__status"] != ACCOUNT_STATUS_MANUAL:
                            _bank_error("Balances", _row["Balance ID"], "ACCOUNT_LINKED", f"balance manual [{_row['Balance Manual']}] on account [{_row['Account_base']}] not Manual")
                        elif _row["Balance Manual"] is None:
                            if not _row["__carried"]:
                                _balances_deleted.append((_row["Date_base"], _row["Time_base"], _row["Account ID"]))
                        elif _row["__value"] is None:
                            _bank_error("Balances", _row["Balance ID"], "VALUE_UNPARSED", f"balance manual [{_row['Balance Manual']}] unparsed")
                        else:
                            _balances_candidates.append(
                                {
                                    "Date": _row["Date_base"],
                                    "Time": _row["Time_base"],
                                    "Account": _row["Account_base"],
                                    "Account ID": _row["Account ID"],
                                    "Value": _row["__value"],
                                    "Key": _row["Balance ID"],
                                    "From First": _row["From First"],
                                }
                            )
                    _balances_new_df = _balances_rows_df.filter(pl.col("Balance ID").is_null() & pl.col("Balance Manual").is_not_null()).with_columns(
                        pl.coalesce(pl.col("__date"), pl.when(pl.col("Date").is_null()).then(pl.lit(today))).alias("__on"), _bank_name("Account").alias("__name")
                    )
                    if len(_balances_new_df):
                        _balances_new_df = _bank_accounts_resolved(_balances_new_df).join(
                            _accounts_current_df.select(["Account ID", "From First"]), left_on="__account_id", right_on="Account ID", how="left"
                        )
                    for _row in _balances_new_df.iter_rows(named=True):
                        _key = f"row {_row['__tab']}"
                        if _row["__on"] is None or (_row["Time"] is not None and _row["__time"] is None):
                            _bank_error("Balances", _key, "VALUE_UNPARSED", f"date [{_row['Date']}] time [{_row['Time']}] unparsed")
                        elif _row["__value"] is None:
                            _bank_error("Balances", _key, "VALUE_UNPARSED", f"balance manual [{_row['Balance Manual']}] unparsed")
                        elif _row["__account_id"] is None:
                            _bank_error("Balances", _key, "ACCOUNT_NOT_MANUAL", f"account [{_row['Account']}] not one Manual account")
                        else:
                            _balances_candidates.append(
                                {
                                    "Date": _row["__on"],
                                    "Time": BALANCES_MANUAL_TIME if _row["Time"] is None else _row["__time"].strftime("%H:%M:%S"),
                                    "Account": _row["Account"],
                                    "Account ID": _row["__account_id"],
                                    "Value": _row["__value"],
                                    "Key": _key,
                                    "From First": _row["From First"],
                                }
                            )
                    _balances_candidates_df = pl.DataFrame(
                        _balances_candidates, schema={"Date": pl.Date, "Time": pl.Utf8, "Account": pl.Utf8, "Account ID": pl.Utf8, "Value": pl.Float64, "Key": pl.Utf8, "From First": pl.Date}
                    )
                    _manual_df = _balances_all_df.filter(pl.col("__path").str.contains("manual_balances_"))
                    _balances_last_df = _balances_all_df.sort(["Date", "Time"]).group_by("Account ID").agg(pl.col("Balance").drop_nulls().last().alias("__last"))
                    _balances_candidates_df = (
                        _balances_candidates_df.with_columns(pl.struct(["Date", "Time", "Account ID"]).is_duplicated().alias("__duplicated"))
                        .join(_accounts_current_df.select(["Account ID", "Name", "Type"]), on="Account ID", how="left")
                        .join(_balances_last_df, on="Account ID", how="left")
                    )
                    _balances_accepted = []
                    for _row in _balances_candidates_df.iter_rows(named=True):
                        if _row["Date"] > today:
                            _bank_error("Balances", _row["Key"], "DATE_FUTURE", f"account [{_row['Name']}] date [{_row['Date']}] in the future")
                        elif _row["From First"] is not None and _row["From First"] > date(1, 1, 1) and _row["Date"] < _row["From First"]:
                            _bank_error("Balances", _row["Key"], "DATE_BEFORE_FROM", f"account [{_row['Name']}] date [{_row['Date']}] before from [{_row['From First']}]")
                        elif _row["__duplicated"]:
                            _bank_error("Balances", _row["Key"], "BALANCE_DUPLICATE", f"account [{_row['Name']}] date [{_row['Date']}] time [{_row['Time']}] entered twice")
                        else:
                            if (_row["Type"] == ACCOUNT_TYPE_LIABILITY and _row["Value"] > 0) or (_row["Type"] != ACCOUNT_TYPE_LIABILITY and _row["Value"] < 0):
                                _bank_error("Balances", _row["Key"], "BALANCE_SIGN", f"account [{_row['Name']}] type [{_row['Type']}] value [{_row['Value']}]")
                            if _row["__last"] not in (None, 0) and _row["Value"] != 0 and not 1 / BALANCES_MANUAL_JUMP <= abs(_row["Value"] / _row["__last"]) <= BALANCES_MANUAL_JUMP:
                                _bank_error("Balances", _row["Key"], "BALANCE_JUMP", f"account [{_row['Name']}] value [{_row['Value']}] last [{_row['__last']}]")
                            _balances_accepted.append(_row)
                    if _balances_accepted or _balances_deleted:
                        _balances_accepted_df = pl.DataFrame(
                            [
                                {
                                    "Date": _row["Date"],
                                    "Time": _row["Time"],
                                    "Account": _row["Name"] or _row["Account"],
                                    "Balance": _row["Value"],
                                    "Balance Manual": _row["Value"],
                                    "Balance Linked": None,
                                    "Account ID": _row["Account ID"],
                                    "Balance ID": None,
                                }
                                for _row in _balances_accepted
                            ],
                            schema=BALANCES_SCHEMA,
                        )
                        _removed_df = pl.DataFrame(
                            _balances_deleted + [(_row["Date"], _row["Time"], _row["Account ID"]) for _row in _balances_accepted],
                            schema={"Date": pl.Date, "Time": pl.Utf8, "Account ID": pl.Utf8},
                            orient="row",
                        )
                        _merged_df = pl.concat(
                            [_manual_df.drop(["__path", "Balance ID"]).join(_removed_df, on=["Date", "Time", "Account ID"], how="anti"), _balances_accepted_df.drop("Balance ID")],
                            how="diagonal_relaxed",
                        ).with_columns(pl.lit(None, dtype=pl.Utf8).alias("Balance ID"))
                        for _year in sorted({_day.year for _day in [*_removed_df["Date"].to_list(), *_balances_accepted_df["Date"].to_list()]}):
                            _year_path = _bank_path("manual_balances", _year)
                            if _year_path not in files_unreadable:
                                _bank_write(_merged_df.filter(pl.col("Date").dt.year() == _year), _year_path, "sheet edit")
                        merged_counts["balances"] += len(_balances_accepted) + len(_balances_deleted)

        _bank_balances_merged()

        # Capture Categories
        def _bank_categories() -> pl.DataFrame:
            return (
                pl.concat(
                    [
                        pl.DataFrame(schema={**TRANSACTIONS_SCHEMA, "Split": pl.Int64, "Year File": pl.Utf8}),
                        *(
                            bank_transactions_identified(_data_df).with_columns(bank_flag("Vetted"), pl.lit(basename(_path)).alias("Year File"))
                            for _path in _bank_paths("redbark_transactions", "manual_transactions")
                            if (_data_df := _bank_readable(_path, TRANSACTIONS_SCHEMA)) is not None
                        ),
                    ],
                    how="diagonal_relaxed",
                )
                .filter(pl.col("Transaction ID").is_not_null())
                .select(["Transaction ID", "Split", "Year File", "Date", "Account", "Amount", "Description", "Category Manual", "Category Derived", "Vetted"])
            )

        # Log Category Changes
        def _bank_categories_logged(_before_df: pl.DataFrame, _after_df: pl.DataFrame, _source: str):
            _columns = {"Category Manual": "Manual", "Category Derived": "Derived", "Vetted": "Vetted"}
            _changed_df = _after_df.join(_before_df.select(["Transaction ID", "Split", *_columns]), on=["Transaction ID", "Split"], how="inner", suffix=" Before").filter(
                pl.any_horizontal([pl.col(_column).ne_missing(pl.col(f"{_column} Before")) for _column in _columns])
            )
            if len(_changed_df):
                changes_frames.append(
                    _changed_df.select(
                        pl.lit(now.isoformat(timespec="seconds")).alias("Run"),
                        pl.lit(_source).alias("Source"),
                        "Year File",
                        "Transaction ID",
                        pl.col("Split").alias("Part"),
                        "Date",
                        "Account",
                        "Amount",
                        "Description",
                        *(_expression for _column, _name in _columns.items() for _expression in (pl.col(f"{_column} Before").alias(f"{_name} Before"), pl.col(_column).alias(f"{_name} After"))),
                    )
                )

        changes_frames: list[pl.DataFrame] = []
        categories_start_df = _bank_categories()

        # Merge Sheet Transaction Data
        def _bank_parts_valid(_tab, _parts, _key, _whole=True):
            _amounts = {round(_part["__amount"] * 100) for _part in _parts if _part["__amount"] is not None}
            if any(_part["__amount"] is None for _part in _parts) or len(_amounts) != 1:
                _bank_error(_tab, _key, "SPLIT_INVALID", "split parts differ in amount")
                return False
            _amount = _amounts.pop()
            _splits = [round((_part["__split"] if _part["__split"] is not None else _part["__amount"]) * 100) for _part in _parts]
            if any(_split == 0 or (_split > 0) != (_amount > 0) for _split in _splits) or (sum(_splits) != _amount if _whole else sum(_splits) % _amount != 0):
                _bank_error(_tab, _key, "SPLIT_INVALID", f"split parts [{', '.join(str(_split / 100) for _split in _splits)}] do not sum to amount [{_amount / 100}]")
                return False
            return True

        def _bank_manual_valid(_tab, _row, _key):
            _from_first = _row["From First"]
            if _row["__date"] is None or _row["__amount"] is None:
                _bank_error(_tab, _key, "VALUE_UNPARSED", f"date [{_row['Date']}] amount [{_row['Amount']}] unparsed")
            elif _row["__account_id"] is None:
                _bank_error(_tab, _key, "ACCOUNT_NOT_MANUAL", f"account [{_row['Account']}] not one Manual account")
            elif _row["__date"] > today:
                _bank_error(_tab, _key, "DATE_FUTURE", f"date [{_row['__date']}] in the future")
            elif _from_first is not None and _from_first > date(1, 1, 1) and _row["__date"] < _from_first:
                _bank_error(_tab, _key, "DATE_BEFORE_FROM", f"date [{_row['__date']}] before from [{_from_first}]")
            elif abs(round(_row["__amount"] * 100) - _row["__amount"] * 100) > 1e-6:
                _bank_error(_tab, _key, "TRANSACTION_DECIMALS", f"amount [{_row['Amount']}] has more than two decimals")
            elif _row["__amount"] == 0:
                _bank_error(_tab, _key, "TRANSACTION_ZERO", "amount zero outside a placeholder")
            elif _row["Description"] is None or not _row["Description"].strip():
                _bank_error(_tab, _key, "TRANSACTION_DESCRIPTION", "description blank")
            else:
                return True
            return False

        def _bank_vetted(_part, _base_part, _present):
            if not _present:
                return _base_part["Vetted"] if _base_part is not None else None
            if _base_part is not None:
                _category_before = _base_part["Category Manual"] or _base_part["Category Derived"]
                _category_after = _part["Category Manual"] or _base_part["Category Derived"]
                if _category_after != _category_before and _part["__vetted"] == _base_part["Vetted"]:
                    return None
                if (
                    "Category Derived" in _part
                    and _part["__vetted"] == FLAG_YES
                    and _base_part["Vetted"] != FLAG_YES
                    and ((_part["Category Derived"] or "").strip() or None) != _base_part["Category Derived"]
                ):
                    return _base_part["Vetted"]
            return _part["__vetted"]

        def _bank_category_checked(_tab, _key, _category):
            if _category is not None and classifier_usable and _category not in classifier_categories:
                _bank_error(_tab, _key, "CATEGORY_UNKNOWN", f"category manual [{_category}] not on the Classifier tab")

        def _bank_manual_row(_tab, _row, _key, _vetted):
            _bank_category_checked(_tab, _key, _row["Category Manual"])
            return {
                "Date": _row["__date"],
                "Account": _row["Name"],
                "Amount": _row["__amount"],
                "Amount Split": _row["__split"] if _row["__split"] is not None else _row["__amount"],
                "Description": _row["Description"],
                "Bank Code": None,
                "Merchant Code": None,
                "Vetted": _vetted,
                "Category Manual": _row["Category Manual"],
                "Category Derived": None,
                "Account ID": _row["__account_id"],
                "Source ID": _row["Source ID"],
                "Transaction ID": None,
            }

        moved_frames: dict[str, list[pl.DataFrame]] = {}

        def _bank_year_merged(_year):
            _year_raw_df = _bank_raw(sheet_files.get(f"Transactions_{_year}")) if sheet_downloaded else None
            if _year_raw_df is None or len(_year_raw_df) == 0 or not accounts_usable:
                return
            _tab_name = f"Transactions_{_year}"
            _year_missing = [_column for _column in ("Date", "Account", "Amount", "Amount Split", "Description", "Category Manual", "Transaction ID") if _column not in _year_raw_df.columns]
            if _year_missing:
                _bank_error(_tab_name, "tab", "TAB_UNUSABLE", f"columns missing [{', '.join(_year_missing)}]")
                return
            _year_frames: list[pl.DataFrame] = []
            for _path in _bank_year_paths(_year):
                if isfile(_path):
                    _data_df = _bank_readable(_path, TRANSACTIONS_SCHEMA)
                    if _data_df is None:
                        return
                    _year_frames.append(_data_df.with_row_index("__index").with_columns(pl.lit(_path).alias("__path")))
            _year_files_df = bank_transactions_identified(pl.concat([pl.DataFrame(schema={"__index": pl.UInt32, **TRANSACTIONS_SCHEMA, "__path": pl.Utf8}), *_year_frames], how="vertical_relaxed"))
            _accounts_current_df = _bank_accounts_current()
            _year_files_df = _year_files_df.join(
                _accounts_current_df.select(["Account ID", pl.col("Status").alias("__status"), "From First"]), on="Account ID", how="left", maintain_order="left"
            ).with_columns(((pl.col("__status") == ACCOUNT_STATUS_MANUAL) & pl.col("__path").str.contains("manual_transactions_")).fill_null(False).alias("__editable"))
            _vetted_present = "Vetted" in _year_raw_df.columns
            _vetted_text = pl.col("Vetted").str.strip_chars().str.to_lowercase()
            _year_rows_df = (
                _year_raw_df.with_row_index("__tab", offset=2)
                .with_columns([pl.lit(None, dtype=pl.Utf8).alias(_column) for _column in ("Source ID", "Vetted") if _column not in _year_raw_df.columns])
                .with_columns(bank_flag("Vetted").alias("__vetted"), (_vetted_text.is_not_null() & (_vetted_text != "") & bank_flag("Vetted").is_null()).fill_null(False).alias("__vetted_bad"))
                .with_columns([_bank_text(_column).alias(_column) for _column in ("Date", "Account", "Amount", "Amount Split", "Category Manual", "Transaction ID", "Source ID")])
                .with_columns(
                    pl.col("Description").replace("", None),
                    pl.col("Date").str.to_date("%Y-%m-%d", strict=False).alias("__date"),
                    pl.col("Amount").cast(pl.Float64, strict=False).alias("__amount"),
                    pl.col("Amount Split").cast(pl.Float64, strict=False).alias("__split"),
                )
                .with_columns(pl.int_range(1, pl.len() + 1).over("Transaction ID").alias("__part"), pl.len().over("Transaction ID").alias("__parts"))
            )
            _base_df = _year_files_df.filter(pl.col("Transaction ID").is_not_null()).with_columns(
                pl.int_range(1, pl.len() + 1).over("Transaction ID").alias("__part"), pl.len().over("Transaction ID").alias("__parts")
            )
            _compare_df = _year_rows_df.filter(pl.col("Transaction ID").is_not_null()).join(_base_df, on=["Transaction ID", "__part"], how="full", suffix="_base", coalesce=True)
            _differs = (
                pl.col("__tab").is_null()
                | pl.col("Date_base").is_null()
                | (pl.col("__date") != pl.col("Date_base")).fill_null(True)
                | ((pl.col("__amount") * 100).round() != bank_cents("Amount_base")).fill_null(True)
                | ((pl.col("__split") * 100).round() != bank_cents("Amount Split_base")).fill_null(pl.col("__split").is_not_null() | pl.col("Amount Split_base").is_not_null())
                | (pl.col("Description") != pl.col("Description_base")).fill_null(pl.col("Description").is_not_null() | pl.col("Description_base").is_not_null())
                | (pl.col("Category Manual") != pl.col("Category Manual_base")).fill_null(pl.col("Category Manual").is_not_null() | pl.col("Category Manual_base").is_not_null())
                | (
                    pl.lit(_vetted_present)
                    & ((pl.col("__vetted") != pl.col("Vetted_base")).fill_null(pl.col("__vetted").is_not_null() | pl.col("Vetted_base").is_not_null()) | pl.col("__vetted_bad").fill_null(False))
                )
                | (pl.col("__editable").fill_null(False) & (_bank_name("Account") != _bank_name("Account_base")).fill_null(True))
            )
            _changed_ids = set(_compare_df.filter(_differs)["Transaction ID"].drop_nulls().to_list())
            _files_frames = {_path: _year_files_df.filter(pl.col("__path") == _path) for _path in _bank_year_paths(_year)}
            _replaced: dict[str, pl.DataFrame] = {}
            _removed_ids: set[str] = set()
            _merged_before = merged_counts["transactions"]

            _tab_resolved_df = _bank_accounts_resolved(_year_rows_df.with_columns(pl.col("__date").fill_null(today).alias("__on"), _bank_name("Account").alias("__name"))).join(
                _accounts_current_df.select(["Account ID", "Name", "From First"]), left_on="__account_id", right_on="Account ID", how="left", maintain_order="left"
            )
            _base_by_id = {_id: _df.to_dicts() for (_id,), _df in _base_df.partition_by("Transaction ID", as_dict=True).items()}
            _tab_by_id = {_id: _df.to_dicts() for (_id,), _df in _tab_resolved_df.drop_nulls("Transaction ID").partition_by("Transaction ID", as_dict=True).items()}

            def _bank_vetted_parts(_parts, _base_parts):
                return [_bank_vetted(_part, _base_parts[_index if _index < len(_base_parts) else 0], _vetted_present) for _index, _part in enumerate(_parts)]

            def _bank_linked_edit(_transaction_id, _tab_parts, _base_parts) -> pl.DataFrame | None:
                _base = _base_parts[0]
                if any(
                    _part["__date"] != _base["Date"]
                    or _part["__amount"] is None
                    or round(_part["__amount"] * 100) != round(_base["Amount"] * 100)
                    or (_part["Description"] or None) != _base["Description"]
                    or (_part["Source ID"] or None) != _base["Source ID"]
                    for _part in _tab_parts
                ):
                    _bank_error(_tab_name, _transaction_id, "ACCOUNT_LINKED", f"account [{_base['Account']}] edited beyond category manual and amount split")
                    return None
                _split_changed = len(_tab_parts) != len(_base_parts) or any(
                    _tab_part["__split"] is None or round(_tab_part["__split"] * 100) != round(_base_part["Amount Split"] * 100) for _tab_part, _base_part in zip(_tab_parts, _base_parts, strict=False)
                )
                if _split_changed and not _bank_parts_valid(_tab_name, _tab_parts, _transaction_id):
                    return None
                _splits = [_part["__split"] if _part["__split"] is not None else _base["Amount"] for _part in _tab_parts] if _split_changed else [_part["Amount Split"] for _part in _base_parts]
                for _part in _tab_parts:
                    _bank_category_checked(_tab_name, _transaction_id, _part["Category Manual"])
                return pl.DataFrame(
                    [
                        {**{_column: _base[_column] for _column in TRANSACTIONS_SCHEMA}, "Amount Split": _split, "Category Manual": _part["Category Manual"], "Vetted": _vetted}
                        for _part, _split, _vetted in zip(_tab_parts, _splits, _bank_vetted_parts(_tab_parts, _base_parts), strict=True)
                    ],
                    schema=TRANSACTIONS_SCHEMA,
                )

            def _bank_manual_edit(_transaction_id, _tab_parts, _base_parts) -> pl.DataFrame | None:
                if (
                    len(_tab_parts) == 1
                    and len(_base_parts) == 1
                    and _tab_parts[0]["__split"] is not None
                    and _base_parts[0]["Amount Split"] is not None
                    and round(_tab_parts[0]["__split"] * 100) == round(_base_parts[0]["Amount"] * 100)
                ):
                    _tab_parts = [{**_tab_parts[0], "__split": _tab_parts[0]["__amount"]}]
                if (
                    not all(_bank_manual_valid(_tab_name, _part, _transaction_id) for _part in _tab_parts)
                    or len({(_part["__account_id"], _part["__date"], _part["Description"]) for _part in _tab_parts}) != 1
                    or (len(_tab_parts) > 1 and not _bank_parts_valid(_tab_name, _tab_parts, _transaction_id))
                ):
                    return None
                return pl.DataFrame(
                    [_bank_manual_row(_tab_name, _part, _transaction_id, _vetted) for _part, _vetted in zip(_tab_parts, _bank_vetted_parts(_tab_parts, _base_parts), strict=True)],
                    schema=TRANSACTIONS_SCHEMA,
                )

            for _transaction_id in sorted(_changed_ids):
                _base_parts, _tab_parts = _base_by_id.get(_transaction_id), _tab_by_id.get(_transaction_id, [])
                if not _base_parts:
                    continue
                _editable = _base_parts[0]["__editable"]
                if _vetted_bad := next((_part for _part in _tab_parts if _part["__vetted_bad"]), None):
                    _bank_error(_tab_name, _transaction_id, "TRANSACTION_VETTED", f"vetted [{_vetted_bad['Vetted']}] not one of [{', '.join(FLAGS)}]")
                elif not _tab_parts:
                    if _editable:
                        _removed_ids.add(_transaction_id)
                        merged_counts["transactions"] += 1
                elif (_rows_df := (_bank_manual_edit if _editable else _bank_linked_edit)(_transaction_id, _tab_parts, _base_parts)) is not None:
                    _new_year = _rows_df["Date"][0].year
                    if _editable and _new_year != _year and not _bank_writable(_bank_path("manual_transactions", _new_year)):
                        _bank_error(_tab_name, _transaction_id, "FILE_UNREADABLE", f"file [{basename(_bank_path('manual_transactions', _new_year))}] unreadable, edit not saved")
                        continue
                    if _editable and _new_year != _year:
                        _removed_ids.add(_transaction_id)
                        moved_frames.setdefault(_bank_path("manual_transactions", _new_year), []).append(_rows_df)
                    else:
                        _replaced[_transaction_id] = _rows_df
                    merged_counts["transactions"] += 1
            _account_names = set(accounts_df.select(_bank_name("Name"))["Name"].drop_nulls().to_list())
            _placeholders_kept = set()
            _new_groups: dict[tuple, list[dict]] = {}
            for _row in _tab_resolved_df.filter(pl.col("Transaction ID").is_null()).iter_rows(named=True):
                _key = f"row {_row['__tab']}"
                if all(_row[_column] is None for _column in ("Date", "Account", "Amount", "Description")):
                    continue
                if _row["__amount"] == 0 and _row["Description"] == TRANSACTION_PLACEHOLDER_DESCRIPTION and _row["__account_id"] is not None:
                    _placeholders_kept.add(_row["__account_id"])
                elif _row["__account_id"] is None:
                    if _row["__name"] in _account_names:
                        _bank_error(_tab_name, _key, "ACCOUNT_LINKED", f"new row for account [{_row['Account']}] not Manual")
                    else:
                        _bank_error(_tab_name, _key, "ACCOUNT_NOT_MANUAL", f"account [{_row['Account']}] not one Manual account")
                elif _row["__vetted_bad"]:
                    _bank_error(_tab_name, _key, "TRANSACTION_VETTED", f"vetted [{_row['Vetted']}] not one of [{', '.join(FLAGS)}]")
                elif _bank_manual_valid(_tab_name, _row, _key):
                    _new_groups.setdefault((_row["__account_id"], _row["__date"], round(_row["__amount"] * 100), _row["Description"]), []).append(_row)
            _held_keys = set(_year_files_df.select(["Account ID", "Date", bank_cents("Amount"), "Description"]).rows())
            for _group_key, _group_rows in _new_groups.items():
                _key = f"row {_group_rows[0]['__tab']}"
                _split_whole = all(_row["__split"] is None or round(_row["__split"] * 100) == _group_key[2] for _row in _group_rows)
                if not _split_whole and not _bank_parts_valid(_tab_name, _group_rows, _key, _whole=False):
                    continue
                if not _bank_writable(_bank_path("manual_transactions", _group_key[1].year)):
                    _bank_error(_tab_name, _key, "FILE_UNREADABLE", f"file [{basename(_bank_path('manual_transactions', _group_key[1].year))}] unreadable, row not saved")
                    continue
                if (len(_group_rows) > 1 and _split_whole) or _group_key in _held_keys:
                    _bank_error(_tab_name, _key, "MANUAL_DUPLICATE", f"manual transaction [{_group_rows[0]['Description']}] identical to another on the same account and date")
                _rows_df = pl.DataFrame([_bank_manual_row(_tab_name, _row, f"row {_row['__tab']}", _bank_vetted(_row, None, _vetted_present)) for _row in _group_rows], schema=TRANSACTIONS_SCHEMA)
                moved_frames.setdefault(_bank_path("manual_transactions", _group_key[1].year), []).append(_rows_df)
                merged_counts["transactions"] += 1
            _placeholders_dropped = _files_frames[_bank_path("manual_transactions", _year)].filter(pl.col("Transaction ID").is_null() & ~pl.col("Account ID").is_in(list(_placeholders_kept)))
            if merged_counts["transactions"] == _merged_before and len(_placeholders_dropped) == 0:
                return
            for _path, _frame_df in _files_frames.items():
                if _path in files_unreadable:
                    continue
                _kept_placeholders_df = _frame_df.filter(pl.col("Transaction ID").is_null() & pl.col("Account ID").is_in(list(_placeholders_kept))).unique(
                    "Account ID", keep="first", maintain_order=True
                )
                _placeholders_kept -= set(_kept_placeholders_df["Account ID"].to_list())
                _replaced_frames = [
                    _replaced[_transaction_id].with_columns(pl.lit(_index, dtype=pl.UInt32).alias("__index"))
                    for _transaction_id, _index in _frame_df.filter(pl.col("Transaction ID").is_in(list(_replaced))).group_by("Transaction ID", maintain_order=True).agg(pl.col("__index").min()).rows()
                ]
                _kept_df = _frame_df.filter(pl.col("Transaction ID").is_not_null() & ~pl.col("Transaction ID").is_in(list(_removed_ids | set(_replaced))))
                _rebuilt_df = pl.concat([_kept_df, _kept_placeholders_df, *_replaced_frames], how="diagonal_relaxed").sort("__index", maintain_order=True).select(list(TRANSACTIONS_SCHEMA))
                if not _rebuilt_df.equals(_frame_df.select(list(TRANSACTIONS_SCHEMA))):
                    _bank_write(_rebuilt_df, _path, "sheet edit")

        for year in sheet_years:
            _bank_year_merged(year)
        for path, frames in sorted(moved_frames.items()):
            if path not in files_unreadable:
                prior_df = _bank_read(path, TRANSACTIONS_SCHEMA) if isfile(path) else pl.DataFrame(schema=TRANSACTIONS_SCHEMA)
                _bank_write(pl.concat([prior_df, *frames], how="vertical_relaxed"), path, "sheet edit")
        merged_kinds = [ERROR_CODES[error["Code"]][0] for error in errors[merged_errors:] if not ERROR_CODES[error["Code"]][1]]
        self.print_log(
            f"Sheet edits merged [{merged_counts['balances']}] balances [{merged_counts['transactions']}] transactions "
            f"[{merged_kinds.count(plugin.LOG_KIND_ERROR)}] rejected [{merged_kinds.count(plugin.LOG_KIND_WARNING)}] suspect",
            started=started_time,
        )

        # Roll Placeholder Data
        def _bank_placeholders_rolled():
            _started_time = time.time()
            _placeholders_removed, _placeholders_added_count = 0, 0
            if accounts_usable:
                _manual_accounts_df = _bank_accounts_current().filter(pl.col("Status") == ACCOUNT_STATUS_MANUAL)
                _placeholder = TRANSACTION_PLACEHOLDER.fill_null(False)
                _current = _placeholder & (pl.col("Date") == month_start)
                for _path in _bank_paths("manual_transactions"):
                    _manual_file_df = _bank_readable(_path, TRANSACTIONS_SCHEMA)
                    if _manual_file_df is None:
                        continue
                    _rolled_df = _manual_file_df.filter(~_placeholder | (_current & pl.col("Account ID").is_first_distinct().over(_current)))
                    if len(_rolled_df) != len(_manual_file_df):
                        _placeholders_removed += len(_manual_file_df) - len(_rolled_df)
                        self.print_log(f"Placeholders removed [{len(_manual_file_df) - len(_rolled_df)}] from [{basename(_path)}]", level="debug")
                        _bank_write(_rolled_df, _path, "placeholder")
                _current_manual_path = _bank_path("manual_transactions", today.year)
                if _current_manual_path not in files_unreadable and len(_manual_accounts_df):
                    _current_manual_df = _bank_read(_current_manual_path, TRANSACTIONS_SCHEMA) if isfile(_current_manual_path) else pl.DataFrame(schema=TRANSACTIONS_SCHEMA)
                    _placeholder_ids = set(_current_manual_df.filter(TRANSACTION_PLACEHOLDER & (pl.col("Date") == month_start))["Account ID"].to_list())
                    _placeholders_added = [
                        {"Date": month_start, "Account": _row["Name"], "Amount": 0.0, "Amount Split": 0.0, "Description": TRANSACTION_PLACEHOLDER_DESCRIPTION, "Account ID": _row["Account ID"]}
                        for _row in _manual_accounts_df.iter_rows(named=True)
                        if _row["Account ID"] not in _placeholder_ids
                    ]
                    _placeholders_added_count = len(_placeholders_added)
                    if _placeholders_added:
                        self.print_log(f"Placeholders added [{len(_placeholders_added)}] to [{basename(_current_manual_path)}]", level="debug")
                        _bank_write(
                            pl.concat([_current_manual_df, pl.DataFrame(_placeholders_added).with_columns(pl.col("Date").cast(pl.Date))], how="diagonal_relaxed"), _current_manual_path, "placeholder"
                        )
            self.print_log(f"Placeholders removed [{_placeholders_removed}] added [{_placeholders_added_count}]", started=_started_time)

        _bank_placeholders_rolled()

        # Download Balance Data
        started_time = time.time()
        balances_year_path = _bank_path("redbark_balances", today.year)
        balances_previous_year_path = _bank_path("redbark_balances", today.year - 1)
        balances_age_hours = (now.timestamp() - getmtime(balances_year_path)) / 3600 if isfile(balances_year_path) else float("inf")
        balances_due = not plugin.config.disable_source_downloads and (plugin.config.force_downloads or balances_age_hours >= BALANCES_MAX_AGE_HOURS)
        balances_moved = False
        linked_schema = {"Redbark Account ID": pl.Utf8, "Redbark Connection ID": pl.Utf8, "Account ID": pl.Utf8, "From First": pl.Date, "Name": pl.Utf8}
        linked_df = pl.DataFrame(schema=linked_schema)
        balances_year_df = _bank_readable(balances_year_path, BALANCES_SCHEMA) if balances_due and isfile(balances_year_path) else pl.DataFrame(schema=BALANCES_SCHEMA)
        if balances_year_df is None:
            balances_due, balances_year_df = False, pl.DataFrame(schema=BALANCES_SCHEMA)
        if balances_due:
            if accounts_usable:
                linked_df = _bank_accounts_current().filter((pl.col("Status") == ACCOUNT_STATUS_LINKED) & pl.col("Redbark Account ID").is_not_null()).select(list(linked_schema))
            else:
                linked_df = pl.DataFrame(
                    [
                        {
                            "Redbark Account ID": str(account.get("id")),
                            "Redbark Connection ID": str(account.get("connectionId")),
                            "Account ID": bank_record_id(ACCOUNT_ID_NAMESPACE, *_bank_redbark_key(account.get("institutionName"), account.get("accountNumber"))),
                            "From First": None,
                            "Name": str(account.get("name") or ""),
                        }
                        for account in _bank_accounts_fetched("no readable tab")
                        if all(_bank_redbark_key(account.get("institutionName"), account.get("accountNumber")))
                    ],
                    schema=linked_schema,
                )

            def _bank_balances_fetched(_linked_ids) -> pl.DataFrame:
                try:
                    _redbark_balances_file = abspath(f"{self.local_cache}/_redbark_balances.csv")
                    _balances_result = self.redbark_download(
                        [f"/v1/balances?accountIds={','.join(_linked_ids[_index : _index + 100])}" for _index in range(0, len(_linked_ids), 100)],
                        _redbark_balances_file,
                        REDBARK_BALANCES_COLUMNS,
                        ignore=True,
                        paged=False,
                    )
                    _balances_response_df = _balances_result.data_frame
                    if _balances_result.errors or _balances_response_df is None:
                        raise ValueError(_balances_result.errors[0]["Detail"] if _balances_result.errors else "balances download failed")
                    _observed_text = pl.col("observedAt").cast(pl.Utf8).str.strip_chars().str.replace(r"Z$", "+00:00")
                    _response_df = (
                        _balances_response_df.with_columns(
                            pl.col("accountId").cast(pl.Utf8).fill_null(""),
                            pl.col("currentBalance").cast(pl.Utf8).str.strip_chars().cast(pl.Float64, strict=False).alias("__amount"),
                            pl.coalesce(
                                _observed_text.str.to_datetime("%Y-%m-%dT%H:%M:%S%.f%:z", time_zone="UTC", strict=False),
                                _observed_text.str.to_datetime("%Y-%m-%dT%H:%M:%S%.f", strict=False).dt.replace_time_zone("UTC"),
                            )
                            .dt.convert_time_zone(REDBARK_TIMEZONE)
                            .alias("__observed"),
                        )
                        .join(linked_df.unique("Redbark Account ID", keep="last"), left_on="accountId", right_on="Redbark Account ID", how="left", maintain_order="left")
                        .with_columns(
                            (pl.col("Account ID").is_not_null() & ~pl.col("__amount").is_nan() & pl.col("__observed").is_not_null() & ~pl.col("accountId").is_duplicated())
                            .fill_null(False)
                            .alias("__usable")
                        )
                    )
                    for _account_id, _usable, _freshness in _response_df.select(["accountId", "__usable", "freshness"]).iter_rows():
                        if not _usable:
                            _bank_error("Redbark", _account_id, "BALANCE_RESPONSE", "balance unknown, duplicated or without value or observed time")
                        elif _freshness not in (None, "fresh"):
                            _bank_error("Redbark", _account_id, "BALANCE_STALE", f"freshness [{_freshness}]")
                    _readings_df = _response_df.filter("__usable").select(
                        pl.col("__observed").dt.date().alias("Date"),
                        pl.col("__observed").dt.strftime("%H:%M:%S").alias("Time"),
                        pl.col("Name").alias("Account"),
                        pl.col("__amount").alias("Balance"),
                        pl.lit(None, dtype=pl.Float64).alias("Balance Manual"),
                        pl.col("__amount").alias("Balance Linked"),
                        "Account ID",
                        pl.lit(None, dtype=pl.Utf8).alias("Balance ID"),
                    )
                    for _redbark_id in sorted(set(_linked_ids) - set(_response_df["accountId"].to_list())):
                        _bank_error("Redbark", _redbark_id, "BALANCE_ABSENT", "linked account absent from the balances response")
                    if len(_readings_df) == 0:
                        raise ValueError("balances response has no usable balances")
                    return _readings_df
                except Exception as _exception:
                    _bank_error("Redbark", "balances", "BALANCE_RESPONSE", f"balances call failed [{_exception}]")
                    return pl.DataFrame(schema=BALANCES_SCHEMA)

            linked_ids = linked_df["Redbark Account ID"].to_list()
            if len(linked_ids) == 0:
                self.print_log("Balances check skipped, no linked accounts", level="debug")
            else:
                readings_df = _bank_balances_fetched(linked_ids)
                if len(readings_df):
                    readings_df = _bank_accounts_applied(readings_df, accounts_df).select(list(BALANCES_SCHEMA)).unique(["Date", "Time", "Account ID"], keep="last", maintain_order=True)
                    latest_previous_df = _bank_readable(balances_previous_year_path, BALANCES_SCHEMA) if len(balances_year_df) == 0 and isfile(balances_previous_year_path) else None
                    latest_df = (balances_year_df if latest_previous_df is None else latest_previous_df).sort(["Date", "Time"]).group_by("Account ID").agg(pl.col("Balance").last().alias("__latest"))
                    changed_df = (
                        readings_df.join(latest_df, on="Account ID", how="left")
                        .filter(pl.col("__latest").is_null() | ((pl.col("Balance") * 100).round() != (pl.col("__latest") * 100).round()))
                        .select(list(BALANCES_SCHEMA))
                    )
                    changed_count = len(changed_df)
                    balances_moved = changed_count > 0
                    opening = len(balances_year_df.filter(pl.col("Date") >= month_start)) == 0
                    written_df = readings_df.join(balances_year_df, on=["Date", "Time", "Account ID"], how="anti") if opening else changed_df
                    if len(written_df):
                        _bank_write(
                            pl.concat([balances_year_df, written_df], how="vertical_relaxed").unique(["Date", "Time", "Account ID"], keep="last", maintain_order=True),
                            balances_year_path,
                            "opening snapshot" if opening else "balance moved",
                        )
                    if isfile(balances_year_path):
                        os.utime(balances_year_path, (now.timestamp(), now.timestamp()))
                    self.print_log(f"Balances [{changed_count}] changed of [{len(readings_df)}] accounts, opening [{opening}]", started=started_time)
        elif not plugin.config.disable_source_downloads and balances_year_path not in files_unreadable:
            self.add_counter(plugin.CTR_SRC_SOURCES, plugin.CTR_ACT_CACHED)
            self.print_log(f"Balances check skipped, fresh at age [{balances_age_hours:.2f}] hours", level="debug")

        # Download Transaction Data
        started_time = time.time()
        redbark_transactions_file = abspath(f"{self.local_cache}/_redbark_transactions.csv")
        sweep_daily = not isfile(redbark_transactions_file) or datetime.fromtimestamp(getmtime(redbark_transactions_file)).astimezone().date() != today

        def _bank_named(_frame_df: pl.DataFrame) -> pl.DataFrame:
            return _bank_accounts_applied(_frame_df, accounts_df).with_columns(_bank_name("Account").alias("__name"), bank_cents("Amount").alias("__cents"))

        if balances_due and len(linked_df) and (balances_moved or sweep_daily):
            held_frames = [pl.DataFrame(schema={"__index": pl.UInt32, **TRANSACTIONS_SCHEMA, "__path": pl.Utf8})]
            for path in _bank_paths("redbark_transactions", "manual_transactions"):
                held_file_df = _bank_readable(path, TRANSACTIONS_SCHEMA)
                if held_file_df is not None:
                    held_frames.append(held_file_df.with_row_index("__index").with_columns(pl.lit(path).alias("__path")))
            held_df = _bank_named(pl.concat(held_frames, how="vertical_relaxed")).filter(~TRANSACTION_PLACEHOLDER)
            transactions_returned_frames = [pl.DataFrame(schema={**TRANSACTIONS_SCHEMA, "__made": pl.Date})]
            returned_ids: dict[str, set[str]] = {}
            transactions_windows = {}
            held_latest = dict(held_df.filter(pl.col("__path").str.contains("redbark_transactions_")).group_by("Account ID").agg(pl.col("Date").max()).rows())

            def _bank_transactions_fetched(_accounts):
                _paths = {}
                for _account in _accounts:
                    if _account["Account ID"] in held_latest:
                        _from = held_latest[_account["Account ID"]] - timedelta(days=TRANSACTIONS_LEEWAY_DAYS)
                    else:
                        _from = max(_account["From First"] or date(1, 1, 1), today - timedelta(days=TRANSACTIONS_HISTORY_DAYS))
                    transactions_windows[_account["Account ID"]] = _from
                    _paths[_account["Account ID"]] = f"/v1/transactions?connectionId={_account['Redbark Connection ID']}&accountId={_account['Redbark Account ID']}&from={_from}"
                _result = self.redbark_download(list(_paths.values()), redbark_transactions_file, REDBARK_TRANSACTIONS_COLUMNS, ignore=True)
                _failed = {_error["Path"]: _error for _error in _result.errors}
                _rows_df = _result.data_frame
                if _rows_df is None:
                    _rows_df = pl.DataFrame(schema=dict.fromkeys(REDBARK_TRANSACTIONS_COLUMNS, pl.Utf8))
                _returned, _dead = [], []
                for _account in _accounts:
                    _error = _failed.get(_paths[_account["Account ID"]])
                    if _error is None:
                        _account_rows_df = _rows_df.filter(pl.col("accountId") == _account["Redbark Account ID"])
                        _returned.append((_account, _account_rows_df))
                        self.print_log(
                            f"Transactions window account [{_account['Account ID']}] from [{transactions_windows[_account['Account ID']]}] to [{today}] returned [{len(_account_rows_df)}]",
                            level="debug",
                        )
                    elif _error["Status"] == 404:
                        _dead.append(_account)
                    else:
                        _bank_error("Redbark", _account["Account ID"], "TRANSACTION_CALL", f"transactions call failed [{_error['Status'] or _error['Detail']}]")
                return _returned, _dead

            linked_accounts = list(linked_df.iter_rows(named=True))
            returned_rows, dead = _bank_transactions_fetched(linked_accounts)
            gone = [(account, "not found") for account in dead]
            if dead and accounts_usable and _bank_accounts_fetched("dead id"):
                dead_ids = [account["Account ID"] for account in dead]
                _bank_accounts_filled(pl.col("Account ID").is_in(dead_ids), True)
                refreshed = {row["Account ID"]: row for row in _bank_accounts_current().filter(pl.col("Account ID").is_in(dead_ids)).iter_rows(named=True)}
                replacements = {
                    account["Account ID"]: {**account, "Redbark Account ID": row["Redbark Account ID"], "Redbark Connection ID": row["Redbark Connection ID"]}
                    for account in dead
                    if (row := refreshed.get(account["Account ID"])) is not None and row["Redbark Account ID"] != account["Redbark Account ID"]
                }
                gone = [(account, "still not found [no replacement Redbark id]") for account in dead if account["Account ID"] not in replacements]
                if replacements:
                    returned_rows, dead = _bank_transactions_fetched([replacements.get(account["Account ID"], account) for account in linked_accounts])
                    gone += [(account, "still not found [HTTP Error 404]") for account in dead]
            for account, reason in gone:
                _bank_error("Accounts", account["Account ID"], "REDBARK_GONE", f"Redbark id [{account['Redbark Account ID']}] {reason}")
            transaction_valid = (
                pl.col("__amount").is_not_null()
                & ~pl.col("__amount").is_nan()
                & pl.col("__posted").is_not_null()
                & (pl.col("id").fill_null("") != "")
                & ~pl.col("__duplicated")
                & pl.col("status").is_not_null()
            )
            for account, rows_df in returned_rows:
                returned_ids[account["Account ID"]] = set(rows_df["id"].fill_null("").to_list())
                parsed_df = (
                    rows_df.with_columns(pl.col("id").fill_null("").is_duplicated().alias("__duplicated"))
                    .filter(pl.col("status").is_null() | (pl.col("status") == "posted"))
                    .with_columns(
                        pl.col("amount").cast(pl.Float64, strict=False).alias("__amount"),
                        pl.coalesce(_bank_text("postDate"), _bank_text("date")).str.to_date("%Y-%m-%d", strict=False).alias("__posted"),
                        pl.coalesce(_bank_text("date"), _bank_text("postDate")).str.to_date("%Y-%m-%d", strict=False).alias("__made"),
                        pl.col("merchantCategoryCode").fill_null("").str.strip_chars().alias("__merchant"),
                    )
                )
                for transaction_id in parsed_df.filter(~transaction_valid)["id"].to_list():
                    _bank_error("Redbark", transaction_id or "", "TRANSACTION_RESPONSE", "transaction without id, amount, posted date or status, or duplicated")
                transactions_returned_frames.append(
                    parsed_df.filter(transaction_valid).select(
                        [
                            pl.col("__posted").alias("Date"),
                            pl.lit(account.get("Name"), dtype=pl.Utf8).alias("Account"),
                            pl.col("__amount").alias("Amount"),
                            pl.col("__amount").alias("Amount Split"),
                            pl.col("description").fill_null("").alias("Description"),
                            pl.col("category").replace("", None).alias("Bank Code"),
                            pl.when((pl.col("__merchant") != "") & (pl.col("__merchant") != CLASSIFIER_MERCHANT_CODE_NONE)).then(pl.col("__merchant").str.zfill(4)).alias("Merchant Code"),
                            pl.lit(account["Account ID"], dtype=pl.Utf8).alias("Account ID"),
                            pl.col("id").alias("Source ID"),
                            pl.col("__made"),
                        ]
                    )
                )
            transactions_new_df = _bank_named(pl.concat(transactions_returned_frames, how="diagonal_relaxed").select([*TRANSACTIONS_SCHEMA, "__made"])).sort(["Date", "Source ID"])
            window_held_df = held_df.join(
                pl.DataFrame({"Account ID": list(transactions_windows), "__from": list(transactions_windows.values())}, schema={"Account ID": pl.Utf8, "__from": pl.Date}),
                on="Account ID",
                how="left",
                maintain_order="left",
            ).filter(pl.col("__from").is_null() | (pl.col("Date") >= pl.col("__from") - timedelta(days=TRANSACTIONS_MATCH_DAYS)))

            def _bank_matched(_new_df: pl.DataFrame, _held_df: pl.DataFrame) -> dict[int, tuple | None]:
                _new_df = _new_df.with_row_index("__new")
                _matched: dict[int, tuple | None] = dict.fromkeys(_new_df.filter(pl.col("Source ID").is_in(_held_df["Source ID"].drop_nulls().implode()))["__new"].to_list())
                _held_df = _held_df.filter(pl.col("Source ID").is_null()).with_row_index("__held")
                _held_rows = dict(zip(_held_df["__held"].to_list(), zip(_held_df["__path"].to_list(), _held_df["__index"].to_list(), strict=True), strict=True))
                _pairs: list[pl.DataFrame] = []
                for _priority, _keys in enumerate((["__name", "__cents"], ["Account ID", "__cents"])):
                    _pairs.append(
                        _new_df.filter(~pl.col("__new").is_in(list(_matched)))
                        .select(["__new", pl.col("__made").alias("Date"), *_keys])
                        .join(_held_df.select(["__held", pl.col("Date").alias("__held_date"), *_keys]), on=_keys)
                        .select(["__new", "__held", pl.lit(_priority).alias("__priority"), (pl.col("Date") - pl.col("__held_date")).dt.total_days().abs().alias("__distance"), pl.col("__held_date")])
                    )
                _pairs_df = pl.concat(_pairs).filter(pl.col("__distance") <= TRANSACTIONS_MATCH_DAYS).sort(["__new", "__priority", "__distance", "__held_date", "__held"])
                _absorbed = set()
                while len(_pairs_df):
                    _choice_df = _pairs_df.group_by("__new", maintain_order=True).first().sort(["__priority", "__distance", "__held_date", "__new"]).unique("__held", keep="first", maintain_order=True)
                    _matched.update({_new: _held_rows[_held] for _new, _held in zip(_choice_df["__new"].to_list(), _choice_df["__held"].to_list(), strict=True)})
                    _absorbed.update(_choice_df["__held"].to_list())
                    _pairs_df = _pairs_df.filter(~pl.col("__new").is_in(list(_matched)) & ~pl.col("__held").is_in(list(_absorbed)))
                return _matched

            matched = _bank_matched(transactions_new_df, window_held_df)
            fresh_df = transactions_new_df.with_row_index("__new").filter(~pl.col("__new").is_in(list(matched))).select(list(TRANSACTIONS_SCHEMA))
            adopted: dict[str, dict[int, str]] = {}
            new_source_ids = transactions_new_df["Source ID"].to_list()
            for new_index, held in matched.items():
                if held is not None:
                    adopted.setdefault(held[0], {})[held[1]] = new_source_ids[new_index]
            for path, sources in sorted(adopted.items()):
                adopted_df = _bank_read(path, TRANSACTIONS_SCHEMA).with_row_index("__index")
                adopted_df = adopted_df.with_columns(pl.coalesce(pl.col("__index").replace_strict(sources, default=None, return_dtype=pl.Utf8), pl.col("Source ID")).alias("Source ID")).drop("__index")
                _bank_write(adopted_df, path, "source adopted")
                self.print_log(f"Source ids adopted [{len(sources)}] by held transactions in [{basename(path)}]", level="debug")
            for row in window_held_df.filter(
                pl.col("Source ID").is_not_null()
                & pl.col("__from").is_not_null()
                & (pl.col("Date") >= pl.col("__from") + timedelta(days=TRANSACTIONS_POSTING_DAYS))
                & pl.col("__path").str.contains("redbark_transactions_")
            ).iter_rows(named=True):
                if row["Account ID"] in returned_ids and row["Source ID"] not in returned_ids[row["Account ID"]]:
                    _bank_error(f"Transactions_{row['Date'].year}", row["Source ID"], "TRANSACTION_GONE", f"held transaction [{row['Description']}] date [{row['Date']}] no longer listed by Redbark")
            for year in sorted(set(fresh_df["Date"].dt.year().to_list())):
                year_path = _bank_path("redbark_transactions", year)
                if year_path in files_unreadable:
                    continue
                prior_df = _bank_read(year_path, TRANSACTIONS_SCHEMA) if isfile(year_path) else pl.DataFrame(schema=TRANSACTIONS_SCHEMA)
                _bank_write(pl.concat([prior_df, fresh_df.filter(pl.col("Date").dt.year() == year)], how="vertical_relaxed"), year_path, "new transactions")
            self.print_log(
                f"Transactions fetched [{len(transactions_new_df)}] across [{len(returned_rows)}] accounts, trigger [{'moved' if balances_moved else 'daily'}], "
                f"new [{len(fresh_df)}] held [{len(matched)}]",
                started=started_time,
            )

        # Upload Account Data
        if accounts_usable and accounts_raw_df is not None and "Account ID" in accounts_raw_df.columns:
            tab_ids_df = accounts_raw_df.with_row_index("Row", offset=2).select([pl.col("Row").cast(pl.Int64), _bank_text("Account ID").alias("__tab_id")])
            for row_number, account_id in (
                accounts_df.join(tab_ids_df, on="Row").filter(pl.col("__tab_id").is_null() | (pl.col("__tab_id") != pl.col("Account ID"))).select(["Row", "Account ID"]).iter_rows()
            ):
                accounts_writes.append((row_number, {"Account ID": account_id}))
        if accounts_writes or accounts_appends:
            accounts_header = list(accounts_raw_df.columns) if accounts_raw_df is not None else []
            accounts_missing = [column for column in ("Status", "Redbark Account ID", "Redbark Connection ID") if column not in accounts_header]
            if accounts_missing:
                _bank_error("Accounts", "tab", "TAB_UNUSABLE", f"columns missing for Redbark cells [{', '.join(accounts_missing)}]")
            else:
                self.sheet_update(
                    {(row_number, column): value for row_number, cells in accounts_writes for column, value in cells.items()},
                    accounts_appends,
                    sheet_key,
                    "Bank",
                    "Accounts",
                    highlight_cells=[_bank_letter(accounts_header, column) for column in ("From", "Institution", "Number", "Name", "Type", "Status") if column in accounts_header],
                    guard=True,
                    schema=TABS_SCHEMA,
                )

        # Dedupe Transaction Data
        def _bank_transactions_deduped():
            _started_time = time.time()
            _dedupe_paths = (
                _bank_paths("redbark_transactions", "manual_transactions")
                if plugin.config.force_reprocessing or any(basename(_path).startswith(("redbark_transactions_", "manual_transactions_")) for _path in files_changed)
                else []
            )
            _dedupe_count = 0
            if _dedupe_paths:
                _dedupe_frames = [
                    bank_transactions_identified(_data_df).with_row_index("__index").with_columns(pl.lit(_path).alias("__path"))
                    for _path in _dedupe_paths
                    if (_data_df := _bank_readable(_path, TRANSACTIONS_SCHEMA)) is not None
                ]
                if _dedupe_frames:
                    _dedupe_df = (
                        pl.concat(_dedupe_frames, how="vertical_relaxed")
                        .filter(pl.col("Transaction ID").is_not_null())
                        .with_columns(pl.concat_str([pl.col("__path"), pl.col("Transaction ID")], separator="/").alias("__transaction"))
                    )
                    _dedupe_first_df = _dedupe_df.group_by("__transaction", maintain_order=True).first()
                    _exact_df = _dedupe_first_df.filter(pl.col("Source ID").is_not_null() & ~pl.col("Source ID").is_first_distinct())
                    _removed = _exact_df["__transaction"].implode()
                    _dedupe_count = len(_exact_df)
                    for _row in _exact_df.iter_rows(named=True):
                        _bank_error(
                            f"Transactions_{_row['Date'].year}",
                            _row["Source ID"] or _row["Transaction ID"],
                            "DEDUPE_REMOVED",
                            f"duplicate transaction [{_row['Description']}] date [{_row['Date']}] removed from [{basename(_row['__path'])}]",
                        )
                    for _path in sorted(set(_exact_df["__path"].to_list())):
                        _kept_df = (
                            _bank_read(_path, TRANSACTIONS_SCHEMA)
                            .with_row_index("__index")
                            .join(_dedupe_df.filter((pl.col("__path") == _path) & pl.col("__transaction").is_in(_removed)).select("__index"), on="__index", how="anti", maintain_order="left")
                            .drop("__index")
                        )
                        _bank_write(_kept_df, _path, "dedupe")
            self.print_log(f"Dedupe removed [{_dedupe_count}] by source id", started=_started_time)

        _bank_transactions_deduped()

        # Classify Transaction Data
        def _bank_transactions_classified() -> bool:
            _started_time = time.time()
            _classify_all = plugin.config.force_reprocessing or classifier_content_changed
            _classify_paths = (
                _bank_paths("redbark_transactions", "manual_transactions")
                if _classify_all
                else sorted({_path for _path in files_changed if basename(_path).startswith(("redbark_transactions_", "manual_transactions_")) and isfile(_path)})
            )
            _classify_frames = {_path: _data_df for _path in _classify_paths if (_data_df := _bank_readable(_path, TRANSACTIONS_SCHEMA)) is not None}
            _classify_df = pl.concat(
                [
                    pl.DataFrame(schema={"__index": pl.UInt32, **TRANSACTIONS_SCHEMA, "__path": pl.Utf8}),
                    *(_frame_df.with_row_index("__index").with_columns(pl.lit(_path).alias("__path")) for _path, _frame_df in _classify_frames.items()),
                ],
                how="vertical_relaxed",
            ).with_columns(
                _bank_name("Description").fill_null("").alias("__description"),
                TRANSACTION_PLACEHOLDER.alias("__placeholder"),
            )
            _targets_df = _classify_df.filter(~pl.col("__placeholder"))

            def _bank_derived(_matchers: tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]) -> tuple[pl.DataFrame, list[tuple[str, str, str, str]]]:
                _patterns_df, _bank_df, _merchant_df = _matchers
                _problems: list[tuple[str, str, str, str]] = []
                _patterns = _patterns_df["__pattern"].unique().to_list()
                _matched_df = pl.DataFrame(schema={"__description": pl.Utf8, "__pattern_category": pl.Utf8})
                if _patterns and len(_targets_df):
                    _found_df = (
                        _targets_df.select("__description")
                        .unique()
                        .with_columns(pl.col("__description").str.extract_many(_patterns, overlapping=True).alias("__pattern"))
                        .explode("__pattern")
                        .drop_nulls("__pattern")
                        .join(_patterns_df, left_on="__pattern", right_on="__pattern")
                        .with_columns(pl.col("__pattern").str.len_chars().alias("__length"))
                        .filter(pl.col("__length") == pl.col("__length").max().over("__description"))
                    )
                    _ties_df = _found_df.group_by("__description").agg(pl.col("Category").unique().sort(), pl.col("__pattern").unique().sort()).filter(pl.col("Category").list.len() > 1)
                    for _, _categories, _ties in _ties_df.iter_rows():
                        _problems.append(
                            ("Classifier", ", ".join(_ties), "CLASSIFIER_TIE", f"patterns of equal length in categories [{', '.join(_categories)}] match one description, neither applied")
                        )
                    _matched_df = (
                        _found_df.group_by("__description")
                        .agg(pl.col("Category").unique())
                        .filter(pl.col("Category").list.len() == 1)
                        .select(["__description", pl.col("Category").list.first().alias("__pattern_category")])
                    )
                    if _classify_all:
                        _shares_df = (
                            _targets_df.select("__description")
                            .join(_found_df.select(["__description", "__pattern"]).unique(), on="__description")
                            .group_by("__pattern")
                            .len()
                            .filter(pl.col("len") > CLASSIFIER_MATCH_SHARE * max(len(_targets_df), 1))
                        )
                        for _pattern, _count in _shares_df.iter_rows():
                            _problems.append(("Classifier", _pattern, "CLASSIFIER_SHARE", f"pattern matches [{_count}] transactions, over the share"))
                return (
                    _targets_df.join(_matched_df, on="__description", how="left")
                    .join(_merchant_df, on="Merchant Code", how="left")
                    .join(_bank_df, on="Bank Code", how="left")
                    .with_columns(pl.coalesce("__pattern_category", "__merchant", "__bank").alias("__derived"))
                ), _problems

            _held = classifier_holding
            _derived_df = None
            if classifier_usable:
                _derived_df, _problems = _bank_derived((classifier_patterns_df, classifier_bank_df, classifier_merchant_df))
                for _problem in _problems:
                    _bank_error(*_problem)
                _held = _held or (classifier_content_changed and len(_problems) > 0)
            if _held:
                _bank_error("Classifier", "tab", "CLASSIFIER_HELD", "edit held until the tab's errors are fixed, classifying with the last applied tab")
                _derived_df = None
            if _derived_df is None and classifier_snapshot_df is not None:
                _derived_df, _ = _bank_derived(_bank_matchers(classifier_snapshot_df, False))
            if _derived_df is None:
                self.print_log(f"Classified [0] of [{len(_targets_df)}] rows, no usable classifier", started=_started_time)
                return _held
            _effective_before = pl.coalesce("Category Manual", "Category Derived")
            _effective_after = pl.coalesce("Category Manual", "__new")
            _moved = _effective_after.ne_missing(_effective_before)
            _moved_years: dict[int, list[int]] = {}
            for _path, _frame_df in _classify_frames.items():
                _updates_df = _derived_df.filter(pl.col("__path") == _path).select(["__index", "__derived"])
                _classified_df = (
                    _frame_df.with_row_index("__index")
                    .join(_updates_df, on="__index", how="left", maintain_order="left")
                    .with_columns(pl.when(pl.col("__index").is_in(_updates_df["__index"].implode())).then(pl.col("__derived")).otherwise(pl.col("Category Derived")).alias("__new"))
                    .with_columns(_moved.alias("__moved"), (_moved & (bank_flag("Vetted") == FLAG_YES)).fill_null(False).alias("__cleared"))
                )
                _counts = _moved_years.setdefault(_bank_file(_path)[1], [0, 0])
                _counts[0] += int(_classified_df["__moved"].sum())
                _counts[1] += int(_classified_df["__cleared"].sum())
                _classified_df = _classified_df.with_columns(
                    pl.when(pl.col("__moved")).then(pl.lit(None, dtype=pl.Utf8)).otherwise(pl.col("Vetted")).alias("Vetted"), pl.col("__new").alias("Category Derived")
                ).drop(["__index", "__derived", "__new", "__moved", "__cleared"])
                if not _classified_df.equals(_frame_df):
                    _bank_write(_classified_df, _path, "classified")
            for _year, (_moved_count, _cleared_count) in sorted(_moved_years.items()):
                if _moved_count:
                    _bank_error(f"Transactions_{_year}", str(_year), "TRANSACTIONS_MOVED", f"[{_moved_count}] rows changed category by the classifier, [{_cleared_count}] ticks cleared")
            self.print_log(
                f"Classified [{_derived_df['__derived'].is_not_null().sum()}] of [{len(_targets_df)}] rows with the [{'last applied' if _held or not classifier_usable else 'live'}] tab, "
                f"moved [{sum(_year_counts[0] for _year_counts in _moved_years.values())}] ticks cleared [{sum(_year_counts[1] for _year_counts in _moved_years.values())}]",
                started=_started_time,
            )
            return _held

        categories_classifying_df = _bank_categories()
        classifier_held = _bank_transactions_classified()
        _bank_categories_logged(categories_start_df, categories_classifying_df, CHANGES_SOURCE_SHEET)
        _bank_categories_logged(categories_classifying_df, _bank_categories(), CHANGES_SOURCE_CLASSIFIER)

        # Process File List
        started_time = time.time()
        for file_path in sorted(files_unreadable):
            _bank_changed(file_path, "unreadable")
        accounts_changed = accounts_usable and (accounts_snapshot_df is None or not accounts_snapshot_df.equals(accounts_df.select(list(ACCOUNTS_SCHEMA))))
        for file_path in files_changed:
            bank_files[file_path] = plugin.DownloadResult(plugin.DownloadStatus.DOWNLOADED, [file_path])
        for file_path in _bank_paths("redbark", "manual"):
            bank_files.setdefault(file_path, plugin.DownloadResult(plugin.DownloadStatus.CACHED, [file_path]))
        if plugin.config.force_reprocessing:
            bank_files = {file_path: plugin.DownloadResult(plugin.DownloadStatus.DOWNLOADED, [file_path]) for file_path in bank_files if isfile(file_path)}

        def _bank_downloaded(_family):
            return {_file_path for _file_path, _result in bank_files.items() if _bank_file(_file_path)[0] == _family and _result.file_status == plugin.DownloadStatus.DOWNLOADED}

        balances_current_file = abspath(f"{self.local_cache}/__bank_balances_current.csv")
        transactions_current_file = abspath(f"{self.local_cache}/__bank_transactions_current.csv")
        balances_rebuild = plugin.config.force_reprocessing or accounts_changed or len(_bank_downloaded("manual_balances")) > 0 or not isfile(balances_current_file)
        balances_new_data = (
            any(_bank_file(file_path)[0] in ("redbark_balances", "manual_balances") for file_path in bank_files)
            and (balances_rebuild or len(_bank_downloaded("redbark_balances")) > 0)
            or (balances_rebuild and isfile(balances_current_file))
        )
        transactions_rebuild = plugin.config.force_reprocessing or accounts_changed or classifier_changed or not isfile(transactions_current_file)
        transactions_years = sorted(
            {
                _bank_file(file_path)[1]
                for file_path in bank_files
                if _bank_file(file_path)[0] in ("redbark_transactions", "manual_transactions") and (transactions_rebuild or bank_files[file_path].file_status == plugin.DownloadStatus.DOWNLOADED)
            }
        )
        transactions_new_data = len(transactions_years) > 0 or (transactions_rebuild and isfile(transactions_current_file))
        files_changed_count = sum(1 for result in bank_files.values() if result.file_status == plugin.DownloadStatus.DOWNLOADED)
        self.print_log(
            f"Files changed [{files_changed_count}] and cached [{len(bank_files) - files_changed_count}], accounts changed [{accounts_changed}] classifier changed [{classifier_changed}]",
            started=started_time,
        )

        def _bank_collected(_file_path: str, _schema: dict) -> pl.DataFrame | None:
            try:
                _data_df = _bank_read(_file_path, _schema)
                _data_df = _data_df.with_columns(bank_flag("Vetted")) if "Vetted" in _schema else _data_df
                if _data_df["Account ID"].null_count() or _data_df["Date"].null_count():
                    raise ValueError("rows without an account id or date")
                self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_PROCESSED)
                return _data_df
            except Exception as _exception:
                self.print_log(f"Unexpected error reading [{_file_path}]", exception=_exception)
                self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_ERRORED)
                return None

        def _bank_bucketed(_transactions_df: pl.DataFrame) -> pl.DataFrame:
            _buckets_df = classifier_df.select(["Category", "Bucket"]).drop_nulls("Category").unique("Category", keep="first", maintain_order=True)
            return (
                _transactions_df.drop("Bucket", strict=False)
                .with_columns(pl.coalesce("Category Manual", "Category Derived").alias("Category"))
                .join(_buckets_df, on="Category", how="left", maintain_order="left")
            )

        # Collect Balance Data
        started_time = time.time()
        balances_df = pl.DataFrame(schema=BALANCES_STATE_SCHEMA)
        balances_frames: list[pl.DataFrame] = []
        if balances_new_data:
            for file_path in sorted(bank_files):
                family = _bank_file(file_path)[0]
                if family not in ("redbark_balances", "manual_balances") or not isfile(file_path):
                    continue
                if family == "manual_balances" or balances_rebuild or bank_files[file_path].file_status == plugin.DownloadStatus.DOWNLOADED:
                    file_df = _bank_collected(file_path, BALANCES_SCHEMA)
                    if file_df is not None:
                        balances_frames.append(file_df)
                else:
                    self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_SKIPPED)
            if balances_frames:
                balances_read_df = pl.concat(balances_frames, how="vertical_relaxed").with_columns(pl.col("Time").str.zfill(8))
                balances_df = bank_balances_identified(
                    pl.concat([balances_read_df, _bank_balances_carried(balances_read_df)], how="vertical_relaxed")
                    .with_columns(pl.coalesce("Balance Manual", "Balance Linked").alias("Balance"))
                    .unique(BALANCES_KEY_COLUMNS, keep="first", maintain_order=True)
                )
                balances_df = _bank_accounts_applied(balances_df, accounts_df).select(list(BALANCES_STATE_SCHEMA)).sort(BALANCES_KEY_COLUMNS)
        self.print_log(f"DataFrame [Balances] collected with [{len(balances_df)}] rows across [{len(balances_frames)}] files", started=started_time)

        # Collect Transaction Data
        started_time = time.time()
        transactions_frames = [pl.DataFrame(schema=TRANSACTIONS_STATE_SCHEMA)]
        transactions_placeholders_frames = [pl.DataFrame(schema=TRANSACTIONS_SCHEMA)]
        transactions_years_read = []
        transactions_files_count = 0
        for file_path in sorted(bank_files):
            if _bank_file(file_path)[0] in ("redbark_transactions", "manual_transactions") and _bank_file(file_path)[1] not in transactions_years:
                self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_SKIPPED)
        for year in transactions_years:
            year_frames = []
            year_readable = True
            for family in ("manual_transactions", "redbark_transactions"):
                file_path = _bank_path(family, year)
                if isfile(file_path):
                    file_df = _bank_collected(file_path, TRANSACTIONS_SCHEMA)
                    year_readable = year_readable and file_df is not None
                    if file_df is not None:
                        year_frames.append(file_df)
                        transactions_files_count += 1
            if not year_readable:
                self.print_log(f"Year [{year}] left as committed, a file of it unreadable", level="warn")
                continue
            transactions_years_read.append(year)
            if year_frames:
                year_df = bank_transactions_identified(pl.concat(year_frames, how="vertical_relaxed"))
                transactions_placeholders_frames.append(year_df.filter(pl.col("Transaction ID").is_null()).select(list(TRANSACTIONS_SCHEMA)))
                transactions_frames.append(_bank_bucketed(_bank_accounts_applied(year_df.filter(pl.col("Transaction ID").is_not_null()), accounts_df)).select(list(TRANSACTIONS_STATE_SCHEMA)))
        transactions_placeholders_df = pl.concat(transactions_placeholders_frames, how="vertical_relaxed")
        transactions_df = pl.concat(transactions_frames, how="vertical_relaxed").sort(TRANSACTIONS_KEY_COLUMNS)
        self.print_log(f"DataFrame [Transactions] collected with [{len(transactions_df)}] rows across [{transactions_files_count}] files", started=started_time)
        for row in transactions_df.filter(pl.struct(TRANSACTIONS_KEY_COLUMNS).is_duplicated()).unique(TRANSACTIONS_KEY_COLUMNS).iter_rows(named=True):
            _bank_error(f"Transactions_{row['Date'].year}", row["Transaction ID"], "TRANSACTION_KEY", f"transaction [{row['Description']}] date [{row['Date']}] keyed twice")

        balances_delta_df = pl.DataFrame(schema=BALANCES_STATE_SCHEMA)
        transactions_delta_df = pl.DataFrame(schema=TRANSACTIONS_STATE_SCHEMA)
        committed = True
        try:

            def _balances_aggregate_function(_data_df):
                return _data_df.select(list(BALANCES_STATE_SCHEMA)).with_columns(cs.float().round(2))

            def _transactions_aggregate_function(_data_df):
                return _data_df.select(list(TRANSACTIONS_STATE_SCHEMA)).with_columns(cs.float().round(2))

            # Commit Balance Data: manual, carried and Redbark readings joined to their accounts → committed state (delta for egress)
            if balances_new_data and (len(balances_df) or balances_rebuild):
                balances_delta_df, _, _ = self.state_cache(balances_df, _balances_aggregate_function, key_columns=BALANCES_KEY_COLUMNS, rebuild=balances_rebuild, name="bank_balances")
                if not isfile(balances_current_file):
                    self.csv_write(pl.DataFrame(schema=BALANCES_STATE_SCHEMA), balances_current_file, print_rows=0)

            # Commit Transaction Data: each changed year of Redbark, history and manual transactions joined to their accounts and buckets → committed state (delta for egress)
            if transactions_new_data and (transactions_years_read or transactions_rebuild):
                transactions_delta_df, _, _ = self.state_cache(
                    transactions_df,
                    _transactions_aggregate_function,
                    key_columns=TRANSACTIONS_KEY_COLUMNS,
                    rebuild=transactions_rebuild,
                    name="bank_transactions",
                    replace=None if transactions_rebuild else pl.col("Date").dt.year().is_in(transactions_years_read),
                )
                if not isfile(transactions_current_file):
                    self.csv_write(pl.DataFrame(schema=TRANSACTIONS_STATE_SCHEMA), transactions_current_file, print_rows=0)
        except Exception as exception:
            committed = False
            self.print_log("Unexpected error processing bank data", exception=exception)
            self.counters_set_all_errored(plugin.CTR_SRC_FILES)

        # Process Data
        started_time = time.time()
        checked_errors = len(errors)
        balances_current_df = (
            self.csv_read(balances_current_file, schema=BALANCES_STATE_SCHEMA, print_rows=0).select(list(BALANCES_STATE_SCHEMA))
            if isfile(balances_current_file)
            else pl.DataFrame(schema=BALANCES_STATE_SCHEMA)
        )
        transactions_current_df = (
            self.csv_read(transactions_current_file, schema=TRANSACTIONS_STATE_SCHEMA, print_rows=0).select(list(TRANSACTIONS_STATE_SCHEMA))
            if isfile(transactions_current_file)
            else pl.DataFrame(schema=TRANSACTIONS_STATE_SCHEMA)
        )
        if len(accounts_df):
            for account_id, account in (
                pl.concat([balances_current_df.select(["Account ID", "Account"]), transactions_current_df.select(["Account ID", "Account"])])
                .filter(~pl.col("Account ID").is_in(accounts_df["Account ID"].implode()))
                .unique("Account ID")
                .sort("Account ID")
                .iter_rows()
            ):
                _bank_error("Accounts", account_id, "ACCOUNT_UNMAPPED", f"account [{account}] on no Accounts row")
            closed_ids = _bank_accounts_current().filter(pl.col("Status") == ACCOUNT_STATUS_CLOSED)["Account ID"].implode()
            for name, day in (
                pl.concat([balances_current_df.select(["Date", "Account", "Account ID"]), transactions_current_df.select(["Date", "Account", "Account ID"])])
                .drop_nulls("Account")
                .filter(~pl.col("Account ID").is_in(closed_ids))
                .group_by(["Account", "Date"])
                .agg(pl.col("Account ID").n_unique().alias("__accounts"))
                .filter(pl.col("__accounts") > 1)
                .select(["Account", "Date"])
                .sort(["Account", "Date"])
                .iter_rows()
            ):
                _bank_error("Accounts", name, "ACCOUNT_NAME_SHARED", f"two accounts hold the name on [{day}]")
            twins_df = (
                transactions_current_df.unique("Transaction ID", keep="first", maintain_order=True)
                .drop_nulls("Account")
                .select(
                    [
                        "Date",
                        "Account",
                        "Account ID",
                        "Transaction ID",
                        bank_cents("Amount").alias("__cents"),
                        _bank_name("Description").fill_null("").alias("__description"),
                    ]
                )
            )
            for row in (
                twins_df.join(twins_df, on=["Account", "Date", "__cents", "__description"], suffix="_other")
                .filter((pl.col("Account ID") != pl.col("Account ID_other")) & (pl.col("Transaction ID") > pl.col("Transaction ID_other")))
                .sort(["Date", "Transaction ID"])
                .iter_rows(named=True)
            ):
                _bank_error(
                    f"Transactions_{row['Date'].year}",
                    row["Transaction ID"],
                    "TRANSACTION_TWO_ACCOUNTS",
                    f"same date, amount and description as transaction [{row['Transaction ID_other']}] on another account named [{row['Account']}]",
                )
            for account_id, name, latest in (
                _bank_accounts_current()
                .filter(pl.col("Status") == ACCOUNT_STATUS_MANUAL)
                .join(balances_current_df.filter(pl.col("Balance Linked").is_null()).group_by("Account ID").agg(pl.col("Date").max().alias("__latest")), on="Account ID", how="left")
                .select(["Account ID", "Name", "__latest"])
                .sort("Account ID")
                .iter_rows()
            ):
                if latest is None:
                    _bank_error("Balances", name, "BALANCE_MANUAL_STALE", f"manual account [{account_id}] has no reading")
                elif (today - latest).days > BALANCES_MANUAL_STALE_DAYS:
                    _bank_error("Balances", name, "BALANCE_MANUAL_STALE", f"manual account [{account_id}] latest reading [{latest}] older than [{BALANCES_MANUAL_STALE_DAYS}] days")
        self.print_log(f"Accounts checked with [{len(errors) - checked_errors}] problems", started=started_time)
        started_time = time.time()
        if len(classifier_df):
            for category in sorted(set(transactions_current_df.filter(pl.col("Category").is_not_null() & pl.col("Bucket").is_null())["Category"].to_list())):
                _bank_error("Classifier", category, "CLASSIFIER_UNBUCKETED", "category in use but not on the Classifier tab")
        review_df = (
            transactions_current_df.with_columns(
                pl.col("Category").is_null().alias("__unclassified"), (pl.col("Vetted") != FLAG_YES).fill_null(True).alias("__unvetted"), (pl.col("Date") >= month_start).alias("__open")
            )
            .group_by([pl.col("Date").dt.year().alias("__year"), "__open"])
            .agg(pl.len().alias("__total"), pl.col("__unclassified").sum(), pl.col("__unvetted").sum())
            .sort(["__year", "__open"])
        )
        open_df = review_df.filter(pl.col("__open"))
        self.print_log(
            f"Transactions unclassified [{review_df['__unclassified'].sum()}] unvetted [{review_df['__unvetted'].sum()}] of [{len(transactions_current_df)}], open month "
            f"unclassified [{open_df['__unclassified'].sum()}] unvetted [{open_df['__unvetted'].sum()}] of [{open_df['__total'].sum()}]",
            started=started_time,
        )
        for year, is_open, total, unclassified, unvetted in review_df.iter_rows():
            for count, code, label in ((unclassified, "TRANSACTIONS_UNCLASSIFIED", "unclassified"), (unvetted, "TRANSACTIONS_UNVETTED", "unvetted")):
                if count:
                    _bank_error(f"Transactions_{year}", str(year), f"{code}_CURRENT" if is_open else code, f"[{count}] of [{total}] {label} in {'open month' if is_open else 'closed months'}")
        for month, change in (
            balances_current_df.filter(pl.col("Balance Linked").is_not_null())
            .sort(["Date", "Time"])
            .group_by(["Account ID", pl.col("Date").dt.month_start().alias("__month")])
            .agg(pl.col("Balance").last())
            .sort("__month")
            .with_columns(pl.col("Balance").diff().over("Account ID").alias("__change"))
            .filter(pl.col("__month") < month_start)
            .select(["__month", "__change"])
            .drop_nulls()
            .tail(PL_PRINT_ROWS)
            .iter_rows()
        ):
            self.print_log(f"Balance change month [{month}] change [{change}]", level="debug")

        # Upload Data
        upload_started_time = time.time()
        tabs_uploaded, tabs_unchanged, tabs_moved, tabs_failed = [], [], [], []

        def _bank_tab_uploaded(_tab, _render_df, _raw_columns, _formula_columns, _dropdown_columns, _highlight_cells, _schema, _before=None, _after=None):
            if tabs_moved:
                tabs_moved.append(_tab)
                return
            _status = self.sheet_upload(
                _render_df,
                sheet_key,
                workbook_name="Bank",
                sheet_name=_tab,
                add_filter=True,
                raw_columns=_raw_columns,
                formula_columns=_formula_columns,
                dropdown_columns=_dropdown_columns,
                highlight_cells=_highlight_cells,
                sheet_before=_before,
                sheet_after=_after,
                guard=True,
                schema=_schema,
            )
            {plugin.UploadStatus.UNCHANGED: tabs_unchanged, plugin.UploadStatus.MOVED: tabs_moved, plugin.UploadStatus.FAILED: tabs_failed}.get(_status, tabs_uploaded).append(_tab)

        if committed:
            self.sheet_ensure(
                sheet_key,
                "Bank",
                {
                    "Summary": [],
                    "Logs": list(plugin.LOG_SCHEMA),
                    "Classifier": list(CLASSIFIER_SCHEMA),
                    "Accounts": ACCOUNTS_TAB_COLUMNS,
                    "Balances": list(BALANCES_SCHEMA),
                    "Transactions": list(TRANSACTIONS_TAB_SCHEMA),
                },
            )
            accounts_current_df = _bank_accounts_current()

            # Upload Balance Data
            if len(balances_current_df) and (len(balances_delta_df) or sheet_downloaded or plugin.config.force_reprocessing):
                started_time = time.time()
                balances_active_df = balances_current_df.join(accounts_current_df, on="Account ID", how="left").filter(pl.col("Status").fill_null("") != ACCOUNT_STATUS_CLOSED)
                balances_sheet_df = (
                    pl.concat(
                        [
                            balances_active_df.filter(pl.col("Date") >= previous_month_start),
                            balances_active_df.filter(pl.col("Date") < previous_month_start).sort(["Date", "Time"]).group_by("Account ID").last(),
                        ],
                        how="diagonal_relaxed",
                    )
                    .sort(["Account", "Date", "Time"], descending=[False, True, True])
                    .select(list(BALANCES_SCHEMA))
                )
                dataframe_print(self.name, balances_sheet_df, print_label="Balances", print_verb="rendered", started=started_time)
                _bank_tab_uploaded(
                    "Balances", balances_sheet_df, BALANCES_RAW_COLUMNS, {"Balance": BALANCES_BALANCE_FORMULA}, {}, [_bank_letter(list(BALANCES_SCHEMA), "Balance Manual")], BALANCES_SCHEMA
                )

            # Upload Transactions Year Data
            transactions_tab_years = sorted(
                set(transactions_years_read)
                | ({int(tab.rsplit("_", 1)[-1]) for tab in sheet_files if re.fullmatch(r"Transactions_\d{4}", tab)} if sheet_downloaded or plugin.config.force_reprocessing else set())
            )
            manual_ids = set(accounts_current_df.filter(pl.col("Status") == ACCOUNT_STATUS_MANUAL)["Account ID"].to_list())
            sheet_columns = list(TRANSACTIONS_YEAR_TAB_SCHEMA)
            for year in transactions_tab_years:
                started_time = time.time()
                year_placeholders_df = transactions_placeholders_df.filter(pl.col("Date").dt.year() == year)
                manual_path = _bank_path("manual_transactions", year)
                if year not in transactions_years_read and isfile(manual_path) and (manual_df := _bank_readable(manual_path, TRANSACTIONS_SCHEMA)) is not None:
                    year_placeholders_df = manual_df.filter(TRANSACTION_PLACEHOLDER).select(list(TRANSACTIONS_SCHEMA))
                year_sheet_df = pl.concat(
                    [transactions_current_df.filter(pl.col("Date").dt.year() == year), _bank_bucketed(year_placeholders_df).with_columns(pl.lit(None, dtype=pl.Int64).alias("Split"))],
                    how="diagonal_relaxed",
                )
                if len(year_sheet_df) == 0:
                    continue
                year_sheet_df = year_sheet_df.sort(["Date", "Account", "Amount", "Transaction ID", "Split"], descending=[True, False, False, False, False], nulls_last=True, maintain_order=True)
                year_rows = [index + 2 for index, account_id in enumerate(year_sheet_df["Account ID"].to_list()) if account_id in manual_ids]
                year_sheet_df = year_sheet_df.select(sheet_columns)
                dataframe_print(self.name, year_sheet_df, print_label=f"Transactions_{year}", print_verb="rendered", started=started_time)
                _bank_tab_uploaded(
                    f"Transactions_{year}",
                    year_sheet_df,
                    TRANSACTIONS_RAW_COLUMNS,
                    {"Category": TRANSACTIONS_CATEGORY_FORMULA, "Bucket": TRANSACTIONS_BUCKET_FORMULA},
                    {"Vetted": FLAGS, "Category Manual": TRANSACTIONS_CATEGORY_OPTIONS},
                    [
                        _bank_letter(sheet_columns, "Amount Split"),
                        _bank_letter(sheet_columns, "Vetted"),
                        _bank_letter(sheet_columns, "Category Manual"),
                        *(f"A{row}:{_bank_letter(sheet_columns, 'Description')}{row}" for row in year_rows),
                    ],
                    TRANSACTIONS_YEAR_TAB_SCHEMA,
                    [f"Transactions_{older}" for older in transactions_tab_years if older < year],
                    ["Transactions", *(f"Transactions_{newer}" for newer in transactions_tab_years if newer > year)],
                )

            # Upload Transactions Tab Data
            transactions_tab_cached_df = self.sheet_cached("Bank", "Transactions")
            transactions_tab_stale = transactions_tab_cached_df is None or transactions_tab_cached_df.head(1).get_column("End of Month", default=pl.Series([])).to_list() != [month_start.isoformat()]
            if len(transactions_current_df) and (len(transactions_delta_df) or transactions_rebuild or transactions_tab_stale):
                transactions_month_df = transactions_current_df.filter(pl.col("Date") < month_start).with_columns(
                    pl.col("Date").dt.month_start().dt.offset_by("1mo").alias("End of Month"),
                    (-pl.col("Amount Split")).alias("__total"),
                    pl.col("Bucket").fill_null(TRANSACTIONS_UNBUCKETED),
                    pl.col("Category").fill_null(TRANSACTIONS_UNCATEGORISED),
                )
                if len(transactions_month_df):
                    started_time = time.time()
                    budgeted_buckets = set(classifier_df.filter(pl.col("Budgeted") == FLAG_YES)["Bucket"].drop_nulls().to_list())
                    transactions_tab_df = (
                        transactions_month_df.group_by(["End of Month", "Bucket", "Category"])
                        .agg(pl.col("__total").sum().round(2).alias("Total"))
                        .filter(pl.col("Total") != 0)
                        .with_columns(pl.when(pl.col("Bucket").is_in(list(budgeted_buckets))).then(pl.lit(FLAG_YES)).otherwise(pl.lit(FLAG_NO)).alias("Budgeted"))
                        .select(list(TRANSACTIONS_TAB_SCHEMA))
                        .sort(["End of Month", "Budgeted", "Bucket", "Category"], descending=[True, True, False, False])
                    )
                    dataframe_print(self.name, transactions_tab_df, print_label="Transactions", print_verb="bucketed", started=started_time)
                    _bank_tab_uploaded(
                        "Transactions",
                        transactions_tab_df,
                        [column for column, dtype in TRANSACTIONS_TAB_SCHEMA.items() if dtype == pl.Utf8],
                        {},
                        {},
                        [],
                        TRANSACTIONS_TAB_SCHEMA,
                        [f"Transactions_{year}" for year in transactions_tab_years],
                    )

        # Log Changes Data
        if changes_frames:
            changes_df = pl.concat(changes_frames, how="vertical_relaxed")
            if drive_failed:
                _bank_error("Bank", "changes", "CHANGES_UNLOGGED", f"[{len(changes_df)}] changed rows not logged, the drive sync failed")
            else:
                changes_file = abspath(f"{self.local_cache}/{CHANGES_FILE_PREFIX}_{today:%Y_%m}.csv")
                changes_md5 = {}
                for year_file in changes_df["Year File"].unique().to_list():
                    year_path = join(self.local_cache, year_file)
                    if isfile(year_path):
                        with open(year_path, "rb") as year_handle:
                            changes_md5[year_file] = hashlib.md5(year_handle.read()).hexdigest()
                changes_df = changes_df.with_columns(pl.col("Year File").replace_strict(changes_md5, default=None, return_dtype=pl.Utf8).alias("File MD5")).select(list(CHANGES_SCHEMA))
                if isfile(changes_file):
                    changes_df = pl.concat([self.csv_read(changes_file, schema=CHANGES_SCHEMA, print_rows=0).select(list(CHANGES_SCHEMA)), changes_df], how="vertical_relaxed")
                self.csv_write(changes_df, changes_file, print_verb="appended", print_rows=0)

        # Upload Logs Data
        logs_df = self.logs_merged(errors, today)
        if committed:
            _bank_tab_uploaded("Logs", logs_df, plugin.LOG_RAW_COLUMNS, {}, {}, [], plugin.LOG_SCHEMA)
        self.print_log(f"Tabs uploaded [{', '.join(tabs_uploaded)}] skipped unchanged [{', '.join(tabs_unchanged)}] skipped moved [{', '.join(tabs_moved)}] failed [{', '.join(tabs_failed)}]")
        self.print_log("Upload complete", started=upload_started_time)

        # Commit Dimension Data
        if committed:
            if len(accounts_df):
                self.csv_write(accounts_df.select(list(ACCOUNTS_SCHEMA)), accounts_snapshot_file, print_rows=0)
            elif isfile(accounts_snapshot_file):
                os.remove(accounts_snapshot_file)
            if len(classifier_df) and not classifier_held:
                self.csv_write(classifier_df.select(list(CLASSIFIER_SCHEMA)), classifier_snapshot_file, print_rows=0)
        if not len(balances_delta_df) and not len(transactions_delta_df):
            self.print_log("No new data found")

    def __init__(self):
        super().__init__("Bank", order=30, repos=REPOS_BANK, error_codes=ERROR_CODES)


def bank_record_id(namespace, *fields):
    def canonical(field):
        if field is None:
            raise ValueError("record identity field is None")
        if isinstance(field, (bool, float, datetime)):
            raise TypeError(f"record identity field type unsupported [{type(field).__name__}]")
        if isinstance(field, str):
            if RECORD_ID_SEPARATOR in field:
                raise ValueError(f"record identity field contains the separator [{field!r}]")
            return re.sub(r"\s+", " ", field).strip()
        if isinstance(field, int):
            return str(field)
        if isinstance(field, date):
            return field.isoformat()
        if isinstance(field, day_time):
            return field.strftime("%H:%M:%S")
        raise TypeError(f"record identity field type unsupported [{type(field).__name__}]")

    if len(fields) == 0:
        raise ValueError("record identity has no fields")
    return uuid.uuid5(namespace, RECORD_ID_SEPARATOR.join(canonical(field) for field in fields)).hex


def bank_flag(column):
    text = pl.col(column).cast(pl.Utf8).str.strip_chars().str.to_lowercase()
    return pl.when(text == FLAG_YES.lower()).then(pl.lit(FLAG_YES)).when(text == FLAG_NO.lower()).then(pl.lit(FLAG_NO)).otherwise(pl.lit(None, dtype=pl.Utf8)).alias(column)


def bank_cents(column):
    return (pl.col(column) * 100).round().cast(pl.Int64)


def bank_balances_identified(balances_df: pl.DataFrame) -> pl.DataFrame:
    balances_df = balances_df.with_columns(pl.col("Time").str.zfill(8))
    return balances_df.with_columns(
        pl.Series("Balance ID", [bank_record_id(BALANCE_ID_NAMESPACE, *identity) for identity in balances_df.select(["Account ID", "Date", "Time"]).iter_rows()], dtype=pl.Utf8)
    )


def bank_transactions_identified(transactions_df: pl.DataFrame) -> pl.DataFrame:
    identity = ["Account ID", "Date", "__cents", "Description"]
    indexed_df = (
        transactions_df.drop(["Split", "Transaction ID"], strict=False)
        .with_row_index("__row")
        .with_columns(
            bank_cents("Amount").alias("__cents"),
            (pl.col("Amount Split").fill_null(pl.col("Amount")) * 100).round().cast(pl.Int64).alias("__split_cents"),
            TRANSACTION_PLACEHOLDER.alias("__placeholder"),
        )
    )
    identified_df = (
        indexed_df.filter(~pl.col("__placeholder"))
        .with_columns((pl.col("__split_cents").cum_sum().over(identity) - pl.col("__split_cents")).alias("__before"))
        .with_columns(pl.when(pl.col("__cents") == 0).then(pl.int_range(pl.len()).over(identity)).otherwise(pl.col("__before") // pl.col("__cents")).alias("__ordinal"))
        .with_columns(pl.when(pl.len().over([*identity, "__ordinal"]) == 1).then(0).otherwise(pl.int_range(1, pl.len() + 1).over([*identity, "__ordinal"])).cast(pl.Int64).alias("Split"))
    )
    identified_df = identified_df.with_columns(
        pl.Series(
            "Transaction ID",
            [bank_record_id(TRANSACTION_ID_NAMESPACE, *key) for key in identified_df.select([*identity, pl.col("__ordinal")]).with_columns(pl.col("Description").fill_null("")).iter_rows()],
            dtype=pl.Utf8,
        )
    )
    return indexed_df.join(identified_df.select(["__row", "Split", "Transaction ID"]), on="__row", how="left").sort("__row").drop(["__row", "__cents", "__split_cents", "__placeholder"])
