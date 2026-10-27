# Bank plugin flow
#   [R] marks what a reprocess changes
#   [F] marks what --force-downloads changes
#   unmarked runs the same on a standard run and a reprocess
#
#     1. Download: bring every source into the cache
#        1.1  Download Drive: pull files changed on Drive, renaming old columns
#        1.2  Download Sheet: read the input tabs, versioning changed ones
#     2. Load: parse the operator's dimension tabs
#        2.1  Load Classifier: parse the rules, holding an edit in error
#        2.2  Load Accounts: parse them, filling Redbark ids weekly or on edit
#     3. Merge: apply operator edits to the golden files
#        3.1  Normalise Files: fill and check manual files changed on Drive     [R] every manual file
#        3.2  Merge Transactions Tabs: take cells edited since the base
#        3.3  Merge Balances Tab: take manual balances edited since the base
#     4. Fetch: add upstream data to the golden files
#        4.1  Fetch Balances: read the linked balances three-hourly
#        4.2  Fetch Transactions: add postings each balance read, sweep weekly  [F] whole history
#        4.3  Import Exports: rename and merge AMEX exports, carry balances     [R] none [F] every export
#        4.4  Dedupe Transactions: drop a source id held twice                  [R] every file
#     5. Derive: compute plugin-owned columns in the files
#        5.1  Classify Transactions: derive categories in changed files         [R] every file
#        5.2  Format Files: rewrite one in an earlier layout or amount format   [R] every file
#     6. Commit: state_cache each changed year, giving its delta                [R] rebuild every year
#        6.1  Commit Balances: readings, manual ones carried to linked moments
#        6.2  Commit Transactions: rows joined to their accounts and buckets
#     7. Check: raise data problems to Logs
#        7.1  Check Accounts: unmapped, shared, unbalanced months, unreconciled
#        7.2  Check Transactions: unclassified, unvetted, unbucketed and spreadsheet errors
#     8. Sync: push changed files, skipping any Drive changed mid-run           [R] verify every file
#        8.1  Sync Drive: upload, or conflict a file Drive moved since 1.1
#     9. Upload: write each changed tab to the sheet                            [R] every tab
#        9.1  Upload Accounts Tab: the Redbark and account ids found
#        9.2  Upload Balances Tab: the recent readings, manual balances blue
#        9.3  Upload Transactions Tabs: each year whose files reached Drive
#        9.4  Upload Summary Tab: closed month totals and what each includes
#        9.5  Upload Logs Tab: this run's problems and the last 30 days'
#    10. Snapshot: move the bases forward for what was persisted
#        10.1 Commit Bases: each tab as uploaded, or as read once on Drive
#        10.2 Log Changes: operator changes to files that reached Drive
#        10.3 Commit Files: the MD5 of each file committed and on Drive

import csv
import glob
import io
import json
import os
import re
import shutil
import time
import uuid
from datetime import UTC, date, datetime, timedelta
from datetime import time as day_time
from decimal import Decimal, InvalidOperation
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
AMOUNT_DECIMALS = 2

REDBARK_TYPE_CREDIT = "credit-card"
REDBARK_TIMEZONE = "Australia/Perth"
REDBARK_INSTITUTION_TIMEZONES = {"HSBC": "Australia/Sydney"}
REDBARK_ACCOUNTS_COLUMNS = ["id", "connectionId", "provider", "name", "type", "institutionName", "accountNumber", "currency"]
REDBARK_BALANCES_COLUMNS = ["accountId", "currentBalance", "availableBalance", "currency", "observedAt", "freshness"]
REDBARK_TRANSACTIONS_COLUMNS = ["id", "accountId", "status", "date", "datetime", "postDate", "amount", "direction", "description", "category", "merchantCategoryCode"]

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
    "Bank Code": pl.Utf8,
    "Merchant Code": pl.Utf8,
    "Pattern": pl.Utf8,
    "Description": pl.Utf8,
    "Notes": pl.Utf8,
}

BALANCES_MAX_AGE_HOURS = 3
BALANCES_MANUAL_JUMP = 10
BALANCES_MANUAL_TIME = "23:59:59"
BALANCES_RECONCILE_DAYS = 35
BALANCES_RECONCILE_SETTLE_DAYS = 7
BALANCES_RECONCILE_IN_FLIGHT = 12
BALANCES_BALANCE_FORMULA = '=IF({Balance Manual}<>"",{Balance Manual},{Balance Auto})'
BALANCE_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "wrangle/balance/v2")
BALANCES_KEY_COLUMNS = ["Date", "Time", "Account ID"]
BALANCES_RAW_COLUMNS = ["Time", "Account", "Account ID", "Balance ID"]
BALANCES_SCHEMA = {
    "Date": pl.Date,
    "Time": pl.Utf8,
    "Account": pl.Utf8,
    "Balance": pl.Float64,
    "Balance Manual": pl.Float64,
    "Balance Auto": pl.Float64,
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
    "Balance Auto": pl.Float64,
    "Balance ID": pl.Utf8,
}

TRANSACTIONS_MATCH_DAYS = 3
TRANSACTIONS_LEEWAY_DAYS = 14
TRANSACTIONS_POSTING_DAYS = 7
TRANSACTIONS_HISTORY_DAYS = 7 * 365 - 7
TRANSACTIONS_SWEEP_DAYS = 90
TRANSACTIONS_SWEEP_EVERY_DAYS = 7
TRANSACTION_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "wrangle/transaction/v1")
TRANSACTIONS_CATEGORY_FORMULA = '=IF({Category Manual}<>"",{Category Manual},{Category Auto})'
TRANSACTIONS_BUCKET_FORMULA = '=IFERROR(VLOOKUP({Category},Classifier!A:B,2,FALSE),"")'
TRANSACTIONS_CATEGORY_OPTIONS = "Classifier!A2:A"
TRANSACTIONS_KEY_COLUMNS = ["Date", "Transaction ID", "Split"]
TRANSACTIONS_RAW_COLUMNS = ["Account", "Description", "Bank Code", "Merchant Code", "Notes", "Vetted", "Category Manual", "Category Auto", "Account ID", "Source ID", "Transaction ID"]
TRANSACTIONS_EDIT_COLUMNS = ["Amount Split", "Category Manual", "Vetted", "Notes"]
TRANSACTIONS_FIXED_COLUMNS = ["Date", "Date Posted", "Account", "Amount", "Description", "Bank Code", "Merchant Code", "Category Auto", "Account ID", "Source ID"]
TRANSACTIONS_AMOUNT_PATTERN = r"^-?\$?-?(\d{1,3}(,\d{3})+|\d+)(\.\d+)?$"
TRANSACTIONS_SPREADSHEET_ERROR_PATTERN = r"^#(NAME\?|REF!|VALUE!|N/A|DIV/0!|NUM!|NULL!|ERROR!|SPILL!|CALC!)$"
TRANSACTIONS_SPREADSHEET_ERROR_COLUMNS = ["Description", "Notes"]
TRANSACTIONS_SCHEMA = {
    "Date": pl.Date,
    "Date Posted": pl.Date,
    "Account": pl.Utf8,
    "Amount": pl.Float64,
    "Amount Split": pl.Float64,
    "Description": pl.Utf8,
    "Bank Code": pl.Utf8,
    "Merchant Code": pl.Utf8,
    "Notes": pl.Utf8,
    "Vetted": pl.Utf8,
    "Category Manual": pl.Utf8,
    "Category": pl.Utf8,
    "Category Auto": pl.Utf8,
    "Account ID": pl.Utf8,
    "Source ID": pl.Utf8,
    "Transaction ID": pl.Utf8,
}
TRANSACTIONS_YEAR_TAB_SCHEMA = {
    "Date": pl.Date,
    "Date Posted": pl.Date,
    "Account": pl.Utf8,
    "Amount": pl.Float64,
    "Amount Split": pl.Float64,
    "Description": pl.Utf8,
    "Bank Code": pl.Utf8,
    "Merchant Code": pl.Utf8,
    "Notes": pl.Utf8,
    "Vetted": pl.Utf8,
    "Category Manual": pl.Utf8,
    "Category": pl.Utf8,
    "Category Auto": pl.Utf8,
    "Bucket": pl.Utf8,
    "End of Month": pl.Date,
    "Account ID": pl.Utf8,
    "Source ID": pl.Utf8,
    "Transaction ID": pl.Utf8,
}
TRANSACTIONS_STATE_SCHEMA = {
    "Date": pl.Date,
    "Transaction ID": pl.Utf8,
    "Split": pl.Int64,
    "Date Posted": pl.Date,
    "Account": pl.Utf8,
    "Account Institution": pl.Utf8,
    "Account Number": pl.Utf8,
    "Account Type": pl.Utf8,
    "Amount": pl.Float64,
    "Amount Split": pl.Float64,
    "Description": pl.Utf8,
    "Bank Code": pl.Utf8,
    "Merchant Code": pl.Utf8,
    "Notes": pl.Utf8,
    "Vetted": pl.Utf8,
    "Category Manual": pl.Utf8,
    "Category": pl.Utf8,
    "Category Auto": pl.Utf8,
    "Bucket": pl.Utf8,
    "Account ID": pl.Utf8,
    "Source ID": pl.Utf8,
}

TRANSACTIONS_BUCKET_EXCLUDED = "Excluded"
TRANSACTIONS_END_OF_MONTH = pl.col("Date").dt.month_start().dt.offset_by("1mo").alias("End of Month")
TRANSACTIONS_TAB_SCHEMA = {
    "End of Month": pl.Date,
    "Bucket": pl.Utf8,
    "Category": pl.Utf8,
    "Total": pl.Float64,
    "Description": pl.Utf8,
}

EXPORT_INSTITUTION_PATTERN = r"(?i)^(american express|amex)$"
EXPORT_NEW_PATTERN = r"^activity.*\.csv$"
EXPORT_NAME_PATTERN = r"^amex_([a-z0-9]+)_transactions_(\d{4}-\d{2}-\d{2})(?:_(\d+))?\.csv$"
EXPORT_COLUMNS = ["Date", "Date Processed", "Description", "Card Member", "Account #", "Amount"]
EXPORT_SCHEMA = {"Date": pl.Date, "Date Posted": pl.Date, "Amount": pl.Float64, "Description": pl.Utf8, "Card": pl.Utf8}
EXPORT_OVERLAP_SHARE = 0.5

TABS_SCHEMA = {**ACCOUNTS_SCHEMA, **CLASSIFIER_SCHEMA, **BALANCES_SCHEMA, **TRANSACTIONS_YEAR_TAB_SCHEMA}
ERROR_CODES = {
    "TAB_UNUSABLE": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_SOURCES),
    "ACCOUNT_DUPLICATE": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_SOURCES),
    "ACCOUNT_FROM": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_SOURCES),
    "ACCOUNT_MISSING": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_SOURCES),
    "ACCOUNT_NAME": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_SOURCES),
    "ACCOUNT_NAME_SHARED": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_SOURCES),
    "ACCOUNT_STATUS": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_SOURCES),
    "ACCOUNT_TYPE": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_SOURCES),
    "ACCOUNT_UNMAPPED": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_SOURCES),
    "REDBARK_GONE": (plugin.LOG_KIND_ERROR, True, True, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_BANK_CODE": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_BUCKET": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_CATEGORY": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_CATEGORY_CASE": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_CODE_LIST": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_CODE_ROWS": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_MERCHANT_CODE": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_PATTERN": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_PATTERN_CONFLICT": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_UNBUCKETED": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_TIE": (plugin.LOG_KIND_WARNING, True, False, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_SHARE": (plugin.LOG_KIND_WARNING, True, False, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_HELD": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_SOURCES),
    "CLASSIFIER_DESCRIPTION": (plugin.LOG_KIND_WARNING, True, False, plugin.CTR_SRC_SOURCES),
    "IMPORT_UNMAPPED": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_SOURCES),
    "IMPORT_UNREADABLE": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_SOURCES),
    "BALANCE_MANUAL_STALE": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_DATA),
    "BALANCE_UNRECONCILED": (plugin.LOG_KIND_ERROR, True, True, plugin.CTR_SRC_DATA),
    "BALANCE_UNRECONCILED_CURRENT": (plugin.LOG_KIND_WARNING, True, False, plugin.CTR_SRC_DATA),
    "BALANCE_ABSENT": (plugin.LOG_KIND_WARNING, True, False, plugin.CTR_SRC_DATA),
    "IMPORT_GONE": (plugin.LOG_KIND_WARNING, True, True, plugin.CTR_SRC_DATA),
    "IMPORT_SUSPECT": (plugin.LOG_KIND_WARNING, True, True, plugin.CTR_SRC_DATA),
    "REDBARK_ACCOUNTS": (plugin.LOG_KIND_INFO, True, False, plugin.CTR_SRC_SOURCES),
    "BALANCE_RESPONSE": (plugin.LOG_KIND_INFO, True, False, plugin.CTR_SRC_SOURCES),
    "BALANCE_STALE": (plugin.LOG_KIND_INFO, True, False, plugin.CTR_SRC_SOURCES),
    "TRANSACTION_CALL": (plugin.LOG_KIND_INFO, True, False, plugin.CTR_SRC_SOURCES),
    "TRANSACTION_RESPONSE": (plugin.LOG_KIND_INFO, True, False, plugin.CTR_SRC_SOURCES),
    "DRIVE_CONFLICT": (plugin.LOG_KIND_ERROR, False, True, plugin.CTR_SRC_SOURCES),
    "DRIVE_DUPLICATE": (plugin.LOG_KIND_ERROR, False, False, plugin.CTR_SRC_SOURCES),
    "TAB_EDIT_IGNORED": (plugin.LOG_KIND_ERROR, False, False, plugin.CTR_SRC_DATA),
    "EDIT_UNMATCHED": (plugin.LOG_KIND_ERROR, False, True, plugin.CTR_SRC_DATA),
    "ACCOUNT_NOT_MANUAL": (plugin.LOG_KIND_ERROR, False, False, plugin.CTR_SRC_DATA),
    "FILE_UNREADABLE": (plugin.LOG_KIND_ERROR, False, False, plugin.CTR_SRC_DATA),
    "VALUE_UNPARSED": (plugin.LOG_KIND_ERROR, False, False, plugin.CTR_SRC_DATA),
    "BALANCE_DUPLICATE": (plugin.LOG_KIND_ERROR, False, False, plugin.CTR_SRC_DATA),
    "DATE_BEFORE_FROM": (plugin.LOG_KIND_ERROR, False, False, plugin.CTR_SRC_DATA),
    "DATE_FUTURE": (plugin.LOG_KIND_ERROR, False, False, plugin.CTR_SRC_DATA),
    "ACCOUNT_LINKED": (plugin.LOG_KIND_ERROR, False, False, plugin.CTR_SRC_DATA),
    "SPLIT_INVALID": (plugin.LOG_KIND_ERROR, False, False, plugin.CTR_SRC_DATA),
    "TRANSACTION_DECIMALS": (plugin.LOG_KIND_ERROR, False, False, plugin.CTR_SRC_DATA),
    "TRANSACTION_DESCRIPTION": (plugin.LOG_KIND_ERROR, False, False, plugin.CTR_SRC_DATA),
    "TRANSACTION_VETTED": (plugin.LOG_KIND_ERROR, False, False, plugin.CTR_SRC_DATA),
    "TRANSACTION_ZERO": (plugin.LOG_KIND_ERROR, False, False, plugin.CTR_SRC_DATA),
    "BALANCE_SIGN": (plugin.LOG_KIND_WARNING, False, True, plugin.CTR_SRC_DATA),
    "BALANCE_JUMP": (plugin.LOG_KIND_WARNING, False, True, plugin.CTR_SRC_DATA),
    "CATEGORY_UNKNOWN": (plugin.LOG_KIND_WARNING, False, False, plugin.CTR_SRC_DATA),
    "MANUAL_DUPLICATE": (plugin.LOG_KIND_WARNING, False, True, plugin.CTR_SRC_DATA),
    "TRANSACTION_GONE": (plugin.LOG_KIND_ERROR, False, True, plugin.CTR_SRC_DATA),
    "TRANSACTION_RELISTED": (plugin.LOG_KIND_WARNING, False, True, plugin.CTR_SRC_DATA),
    "TRANSACTION_UNHELD": (plugin.LOG_KIND_WARNING, False, True, plugin.CTR_SRC_DATA),
    "DEDUPE_REMOVED": (plugin.LOG_KIND_INFO, False, True, plugin.CTR_SRC_DATA),
    "TRANSACTIONS_UNCLASSIFIED": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_DATA),
    "TRANSACTIONS_UNCLASSIFIED_CURRENT": (plugin.LOG_KIND_WARNING, True, False, plugin.CTR_SRC_DATA),
    "TRANSACTIONS_UNVETTED": (plugin.LOG_KIND_ERROR, True, False, plugin.CTR_SRC_DATA),
    "TRANSACTIONS_UNVETTED_CURRENT": (plugin.LOG_KIND_WARNING, True, False, plugin.CTR_SRC_DATA),
    "TRANSACTION_TWO_ACCOUNTS": (plugin.LOG_KIND_WARNING, True, False, plugin.CTR_SRC_DATA),
    "TRANSACTION_SPREADSHEET_ERROR": (plugin.LOG_KIND_WARNING, True, False, plugin.CTR_SRC_DATA),
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
# Remove with the header rewrite in 1.1 once release has run it, every file then holding the new names
COLUMNS_RENAMED = {"Category Derived": "Category Auto", "Balance Linked": "Balance Auto", "Derived Before": "Auto Before", "Derived After": "Auto After"}
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
    "Auto Before": pl.Utf8,
    "Auto After": pl.Utf8,
    "Vetted Before": pl.Utf8,
    "Vetted After": pl.Utf8,
    "Split Before": pl.Float64,
    "Split After": pl.Float64,
    "File MD5": pl.Utf8,
}
CHANGES_SOURCE_SHEET = "sheet"
CHANGES_SOURCE_CLASSIFIER = "classifier"

REPOS_BANK = plugin.Repos(
    preview={
        "drive_folder": "1ELcrbuJxjlYcDJ8FRWacvsKvSM5sypaV",
        "sheet_key": "18SJGNZEsdDRyqkZGn8mxl6c5Ec09fqMgVlyyPYyhXtM",
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
        drive_folder = self.remote_repos.drive_folder
        files_read: dict[tuple[str, tuple], pl.DataFrame] = {}
        files_md5: dict[str, str] = {}
        files_unreadable: set[str] = set()
        files_invalid: set[str] = set()
        files_conflicted: set[str] = set()
        held_cache: list[pl.DataFrame] = []
        years_held: set[int] = set()
        balances_held: set[int] = set()
        errors: list[dict] = []
        files_committed_file = abspath(f"{self.local_cache}/__bank_committed.json")
        files_committed: dict[str, str] = {}
        if isfile(files_committed_file):
            with open(files_committed_file) as files_committed_handle:
                files_committed = json.load(files_committed_handle)

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

        def _bank_file(_path) -> tuple[str, int]:
            _match = cast(re.Match, re.fullmatch(FILE_NAME_PATTERN, basename(_path).lower()))
            return f"{_match[1]}_{_match[2]}", int(_match[3])

        def _bank_paths(*_prefixes):
            return [
                _path
                for _prefix in _prefixes
                for _path in sorted(abspath(_path).lower() for _path in glob.glob(f"{self.local_cache}/{_prefix}_*.csv") if re.fullmatch(FILE_NAME_PATTERN, basename(_path).lower()))
            ]

        def _bank_path(_family, _year):
            return abspath(f"{self.local_cache}/{_family}_{_year}.csv").lower()

        def _bank_read(_path: str, _schema: dict) -> pl.DataFrame:
            _key = (_path, tuple(_schema))
            if _key not in files_read:
                _data_df = self.csv_read(_path, schema=_schema, print_rows=0)
                files_read[_key] = _data_df.with_columns([pl.lit(None, dtype=_dtype).alias(_column) for _column, _dtype in _schema.items() if _column not in _data_df.columns]).select(
                    [pl.col(_column).cast(_dtype) for _column, _dtype in _schema.items()]
                )
            return files_read[_key]

        def _bank_unreadable(_path: str, _exception: Exception):
            files_unreadable.add(_path)
            self.print_log(f"File [{basename(_path)}] unreadable, kept and skipped", exception=_exception)
            self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_ERRORED)

        def _bank_readable(_path: str, _schema: dict) -> pl.DataFrame | None:
            if _path in files_unreadable or _path in files_invalid:
                return None
            try:
                return _bank_read(_path, _schema)
            except Exception as _exception:
                _bank_unreadable(_path, _exception)
                return None

        def _bank_writable(_path: str) -> bool:
            return not isfile(_path) or _bank_readable(_path, TRANSACTIONS_SCHEMA) is not None

        def _bank_rendered(_data_df: pl.DataFrame, _path: str) -> pl.DataFrame:
            if _bank_file(_path)[0].endswith("_balances"):
                return bank_balances_identified(_data_df.select(list(BALANCES_SCHEMA))).sort(["Date", "Time", "Account ID"], descending=[True, True, False], maintain_order=True)
            return (
                bank_transactions_identified(_data_df.select(list(TRANSACTIONS_SCHEMA)))
                .drop("Split")
                .with_columns(pl.col("Merchant Code").cast(pl.Utf8), bank_flag("Vetted").alias("Vetted"))
                .sort(["Date", "Account ID", "Amount", "Description"], descending=[True, False, False, False], maintain_order=True, nulls_last=True)
            )

        def _bank_write(_data_df: pl.DataFrame, _path: str, _verb: str):
            for _key in [_key for _key in files_read if _key[0] == _path]:
                del files_read[_key]
            files_md5.pop(_path, None)
            held_cache.clear()
            _data_df = _bank_rendered(_data_df, _path)
            os.makedirs(dirname(_path), exist_ok=True)
            self.csv_write(_data_df, _path, print_verb=_verb, print_rows=0, float_precision=AMOUNT_DECIMALS)

        def _bank_md5(_path: str) -> str | None:
            if _path not in files_md5 and isfile(_path):
                files_md5[_path] = self._file_md5(_path)
            return files_md5.get(_path)

        def _bank_changed(_path: str) -> bool:
            return plugin.config.force_reprocessing or files_committed.get(basename(_path)) != _bank_md5(_path)

        def _bank_year_frame(_year: int) -> pl.DataFrame | None:
            _frames = [pl.DataFrame(schema={**TRANSACTIONS_SCHEMA, "__index": pl.UInt32, "__path": pl.Utf8})]
            for _family in ("redbark_transactions", "manual_transactions"):
                _path = _bank_path(_family, _year)
                if isfile(_path):
                    _data_df = _bank_readable(_path, TRANSACTIONS_SCHEMA)
                    if _data_df is None:
                        return None
                    _frames.append(_data_df.with_row_index("__index").with_columns(pl.lit(_path).alias("__path")))
            return bank_transactions_identified(pl.concat(_frames, how="diagonal_relaxed").with_columns(bank_flag("Vetted")))

        def _bank_years() -> list[int]:
            return sorted({_bank_file(_path)[1] for _path in _bank_paths("redbark_transactions", "manual_transactions")})

        def _bank_held() -> pl.DataFrame:
            if not held_cache:
                held_cache.append(
                    pl.concat(
                        [
                            pl.DataFrame(schema={**TRANSACTIONS_SCHEMA, "__index": pl.UInt32, "__path": pl.Utf8, "Split": pl.Int64}),
                            *(_year_df for _year in _bank_years() if (_year_df := _bank_year_frame(_year)) is not None),
                        ],
                        how="diagonal_relaxed",
                    ).filter(pl.col("Transaction ID").is_not_null())
                )
            return held_cache[0]

        def _bank_manual_readings() -> pl.DataFrame:
            _frames = [pl.DataFrame(schema={"__index": pl.UInt32, **BALANCES_SCHEMA, "__path": pl.Utf8})]
            for _path in _bank_paths("manual_balances"):
                _data_df = _bank_readable(_path, BALANCES_SCHEMA)
                if _data_df is not None:
                    _frames.append(_data_df.with_row_index("__index").with_columns(pl.lit(_path).alias("__path")))
            return bank_balances_identified(pl.concat(_frames, how="vertical_relaxed").drop_nulls(["Account ID", "Date", "Time"]))

        def _bank_raw(_path: str | None) -> pl.DataFrame | None:
            return pl.read_csv(_path, infer_schema=False, raise_if_empty=False) if _path and isfile(_path) else None

        def _bank_text(_column):
            return pl.col(_column).str.strip_chars().replace("", None)

        def _bank_name(_column):
            return pl.col(_column).str.strip_chars().str.to_lowercase().str.replace_all(r"\s+", " ")

        def _bank_letter(_columns, _column):
            return chr(ord("A") + _columns.index(_column))

        def _bank_error(_tab, _key, _code, _detail):
            self.error(errors, _tab, _key, _code, _detail)

        # 1.1 Download Drive
        if drive_folder is not None and not plugin.config.disable_drive_downloads:
            self.drive_synchronise(drive_folder, self.local_cache, download=True, errors=errors)
        for path in glob.glob(f"{self.local_cache}/*.csv"):
            if basename(path).startswith("_sheet_"):
                continue
            with open(path, encoding="utf-8", newline="") as handle:
                header, rest = handle.readline(), handle.read()
            columns = next(csv.reader([header]), [])
            if set(columns) & set(COLUMNS_RENAMED):
                with open(path, "w", encoding="utf-8", newline="") as handle:
                    csv.writer(handle, lineterminator=header[len(header.rstrip("\r\n")) :] or "\n").writerow([COLUMNS_RENAMED.get(column, column) for column in columns])
                    handle.write(rest)
                self.print_log(f"File [{basename(path)}] columns renamed")

        # 1.2 Download Sheet
        started_time = time.time()
        sheet_years = sorted({*_bank_years(), today.year})
        sheet_tabs = ["Accounts", "Classifier", "Balances", *(f"Transactions_{year}" for year in sheet_years)]
        sheet_results = self.sheet_download(sheet_key, "Bank", sheet_tabs, schema=TABS_SCHEMA)
        sheet_files: dict[str, str] = {tab: result.file_paths[0] for tab, result in sheet_results.items() if result.file_status != plugin.DownloadStatus.FAILED}
        self.print_log(
            f"Sheet tabs downloaded [{', '.join(tab for tab, result in sheet_results.items() if result.file_status == plugin.DownloadStatus.DOWNLOADED)}] "
            f"failed [{', '.join(tab for tab, result in sheet_results.items() if result.file_status == plugin.DownloadStatus.FAILED)}]",
            started=started_time,
        )

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

        # 2.1 Load Classifier
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
                for row in classifier_rows_df.filter(pl.col("Pattern").is_not_null() & pl.col("Description").is_not_null()).iter_rows(named=True):
                    _bank_error("Classifier", f"row {row['Row']}", "CLASSIFIER_DESCRIPTION", f"description on pattern [{row['Pattern']}] row, put it in notes")
                classifier_patterns_df, classifier_bank_df, classifier_merchant_df = _bank_matchers(classifier_rows_df, True)
                classifier_df = classifier_rows_df.drop(["Row", "Bucket"]).join(category_bucket_df, on="Category", how="left", maintain_order="left").select(list(CLASSIFIER_SCHEMA))
            except Exception as exception:
                _bank_error("Classifier", "tab", "TAB_UNUSABLE", f"tab unusable [{exception}]")
        classifier_usable = len(classifier_df) > 0
        classifier_content_changed = classifier_usable and (
            classifier_snapshot_df is None or not classifier_snapshot_df.drop(["Description", "Notes"]).equals(classifier_df.drop(["Description", "Notes"]))
        )
        classifier_holding = classifier_content_changed and any(error["Code"] in CLASSIFIER_HOLDING_CODES for error in errors[classifier_errors_start:])
        classifier_buckets = ["Category", "Bucket"]
        classifier_buckets_df = classifier_df.select(classifier_buckets).unique(maintain_order=True)
        classifier_changed = classifier_usable and (classifier_snapshot_df is None or not classifier_snapshot_df.select(classifier_buckets).unique(maintain_order=True).equals(classifier_buckets_df))
        classifier_categories = set(classifier_df["Category"].to_list())
        self.print_log(
            f"Classifier tab [{len(classifier_df)}] rows, patterns [{len(classifier_patterns_df)}] bank codes [{len(classifier_bank_df)}] "
            f"merchant codes [{len(classifier_merchant_df)}], changed [{classifier_content_changed}] buckets changed [{classifier_changed}]",
            started=started_time,
        )

        # 2.2 Load Accounts
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
                accounts_df = accounts_parsed_df.with_columns(
                    pl.when(pl.col("Type").is_in(ACCOUNT_TYPES)).then(pl.col("Type")).otherwise(pl.lit(ACCOUNT_TYPE_ASSET)).alias("Type"),
                    pl.Series("Account ID", [bank_record_id(ACCOUNT_ID_NAMESPACE, *key) for key in accounts_parsed_df.select(["Institution", "Number"]).iter_rows()], dtype=pl.Utf8),
                )
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
        accounts_current_df = _bank_accounts_current()

        def _bank_categories() -> pl.DataFrame:
            return _bank_held().select(
                [
                    "Transaction ID",
                    "Split",
                    pl.col("__path").str.extract(r"([^/]+)$").alias("Year File"),
                    "Date",
                    "Account",
                    "Amount",
                    "Amount Split",
                    "Description",
                    "Category Manual",
                    "Category Auto",
                    "Vetted",
                ]
            )

        changes_frames: list[pl.DataFrame] = []

        def _bank_categories_logged(_before_df: pl.DataFrame, _after_df: pl.DataFrame, _source: str):
            _columns = {"Category Manual": "Manual", "Category Auto": "Auto", "Vetted": "Vetted", "Amount Split": "Split"}
            _context = ["Year File", "Date", "Account", "Amount", "Description"]
            _ids = _before_df["Transaction ID"].implode()
            _parts_df = (
                _before_df.select(["Transaction ID", "Split", *_columns])
                .rename({_column: f"{_column} Before" for _column in _columns})
                .join(_after_df.filter(pl.col("Transaction ID").is_in(_ids)), on=["Transaction ID", "Split"], how="full", coalesce=True)
                .filter(pl.col("Transaction ID").is_in(_after_df["Transaction ID"].implode()))
                .join(pl.concat([_after_df, _before_df]).unique("Transaction ID", keep="first").select(["Transaction ID", *_context]), on="Transaction ID", how="left", suffix=" Held")
            )
            _operator = ["Category Manual", "Vetted", "Amount Split"] if _source == CHANGES_SOURCE_SHEET else ["Vetted"]
            _changed_df = _parts_df.filter(pl.any_horizontal([pl.col(_column).ne_missing(pl.col(f"{_column} Before")) for _column in _operator]))
            if len(_changed_df):
                changes_frames.append(
                    _changed_df.select(
                        pl.lit(now.isoformat(timespec="seconds")).alias("Run"),
                        pl.lit(_source).alias("Source"),
                        pl.coalesce("Year File", "Year File Held").alias("Year File"),
                        "Transaction ID",
                        pl.col("Split").alias("Part"),
                        *(pl.coalesce(_column, f"{_column} Held").alias(_column) for _column in _context[1:]),
                        *(_expression for _column, _name in _columns.items() for _expression in (pl.col(f"{_column} Before").alias(f"{_name} Before"), pl.col(_column).alias(f"{_name} After"))),
                    )
                )

        def _bank_bucketed(_transactions_df: pl.DataFrame) -> pl.DataFrame:
            _buckets_df = classifier_df.select(["Category", "Bucket"]).drop_nulls("Category").unique("Category", keep="first", maintain_order=True)
            return (
                _transactions_df.drop("Bucket", strict=False)
                .with_columns(pl.coalesce("Category Manual", "Category Auto").alias("Category"))
                .join(_buckets_df, on="Category", how="left", maintain_order="left")
            )

        def _bank_tab_rendered(_rows_df: pl.DataFrame) -> pl.DataFrame:
            return (
                _rows_df.sort(["Date", "Account", "Amount", "Transaction ID", "Split"], descending=[True, False, False, False, False], nulls_last=True, maintain_order=True)
                .with_columns(TRANSACTIONS_END_OF_MONTH)
                .select(list(TRANSACTIONS_YEAR_TAB_SCHEMA))
            )

        # 3.1 Normalise Files
        def _bank_manual_normalised():
            started_time = time.time()
            normalised_counts = {"files": 0, "invalid": 0}

            def _bank_operator_rows(_path: str, _columns: list[str]) -> pl.DataFrame:
                with open(_path, "rb") as _handle:
                    _text = _handle.read().decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
                _raw_df = pl.read_csv(io.StringIO(_text), infer_schema=False, raise_if_empty=False)
                return (
                    _raw_df.with_columns([pl.lit(None, dtype=pl.Utf8).alias(_column) for _column in _columns if _column not in _raw_df.columns])
                    .with_columns([pl.col(_column).str.strip_chars().replace("", None).alias(_column) for _column in _columns])
                    .with_row_index("__row", offset=2)
                )

            def _bank_operator_date(_column):
                return pl.coalesce([pl.col(_column).str.to_date(_date_format, strict=False) for _date_format in plugin.SHEET_DATE_FORMATS])

            def _bank_operator_amount(_column):
                return pl.when(pl.col(_column).str.contains(TRANSACTIONS_AMOUNT_PATTERN)).then(pl.col(_column).str.replace_all(r"[$,]", "").cast(pl.Float64, strict=False))

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

            def _bank_operator_accounts(_rows_df: pl.DataFrame) -> pl.DataFrame:
                return (
                    _bank_accounts_resolved(_rows_df.with_columns(pl.col("__date").alias("__on"), _bank_name("Account").alias("__name")))
                    .with_columns(pl.coalesce("Account ID", "__account_id").alias("__account_id"))
                    .join(
                        accounts_current_df.select(
                            ["Account ID", pl.col("Status").alias("__status"), pl.col("From First").alias("__from_first"), pl.col("Name").alias("__account_name"), pl.col("Type").alias("__type")]
                        ),
                        left_on="__account_id",
                        right_on="Account ID",
                        how="left",
                        maintain_order="left",
                    )
                )

            accounts_names = set(accounts_df.select(_bank_name("Name"))["Name"].drop_nulls().to_list())

            def _bank_operator_checked(_tab, _row) -> bool:
                _key = f"row {_row['__row']}"
                if _row["__date"] is None or _row["__value"] is None:
                    _bank_error(_tab, _key, "VALUE_UNPARSED", f"date [{_row['Date']}] value [{_row['__text']}] unparsed")
                elif _row["__account_id"] is None and _row["__name"] in accounts_names:
                    _bank_error(_tab, _key, "ACCOUNT_LINKED", f"account [{_row['Account']}] not Manual, give its account id to keep a row of it")
                elif _row["__account_id"] is None:
                    _bank_error(_tab, _key, "ACCOUNT_NOT_MANUAL", f"account [{_row['Account']}] not one Manual account")
                elif _row["__date"] > today:
                    _bank_error(_tab, _key, "DATE_FUTURE", f"date [{_row['__date']}] in the future")
                elif _row["__from_first"] is not None and _row["__from_first"] > date(1, 1, 1) and _row["__date"] < _row["__from_first"]:
                    _bank_error(_tab, _key, "DATE_BEFORE_FROM", f"date [{_row['__date']}] before from [{_row['__from_first']}]")
                else:
                    return True
                return False

            normalised_frames: dict[str, pl.DataFrame] = {}
            for path in _bank_paths("manual_transactions"):
                if not _bank_changed(path) or not accounts_usable:
                    continue
                file_name, file_year = basename(path), _bank_file(path)[1]
                try:
                    rows_df = _bank_operator_rows(path, list(TRANSACTIONS_SCHEMA))
                except Exception as exception:
                    _bank_unreadable(path, exception)
                    years_held.add(file_year)
                    continue
                rows_df = _bank_operator_accounts(
                    rows_df.with_columns(
                        _bank_operator_date("Date").alias("__date"),
                        _bank_operator_amount("Amount").alias("__value"),
                        _bank_operator_amount("Amount Split").alias("__split"),
                        _bank_operator_date("Date Posted").alias("__posted"),
                        pl.col("Amount").alias("__text"),
                        bank_flag("Vetted").alias("__vetted"),
                    )
                )
                file_valid = True
                for row in rows_df.iter_rows(named=True):
                    key = f"row {row['__row']}"
                    if not _bank_operator_checked(file_name, row):
                        file_valid = False
                    elif abs(round(row["__value"] * 100) - row["__value"] * 100) > 1e-6:
                        _bank_error(file_name, key, "TRANSACTION_DECIMALS", f"transaction on [{row['__account_name']}] amount [{row['Amount']}] has more than two decimals")
                        file_valid = False
                    elif row["__value"] == 0:
                        _bank_error(file_name, key, "TRANSACTION_ZERO", f"transaction on [{row['__account_name']}] amount zero")
                        file_valid = False
                    elif row["Description"] is None:
                        _bank_error(file_name, key, "TRANSACTION_DESCRIPTION", f"transaction on [{row['__account_name']}] description blank")
                        file_valid = False
                    elif row["Vetted"] is not None and row["__vetted"] is None:
                        _bank_error(file_name, key, "TRANSACTION_VETTED", f"transaction on [{row['__account_name']}] vetted [{row['Vetted']}] not one of [{', '.join(FLAGS)}]")
                        file_valid = False
                    elif (row["Amount Split"] is not None and row["__split"] is None) or (row["Date Posted"] is not None and row["__posted"] is None):
                        _bank_error(file_name, key, "VALUE_UNPARSED", f"transaction on [{row['__account_name']}] amount split [{row['Amount Split']}] date posted [{row['Date Posted']}] unparsed")
                        file_valid = False
                if file_valid:
                    for _, group_df in rows_df.with_columns(pl.coalesce("__split", "__value").alias("__split")).group_by(
                        ["__account_id", "__date", bank_cents("__value"), bank_canonical("Description")], maintain_order=True
                    ):
                        cents, splits = round(group_df["__value"][0] * 100), [round(split * 100) for split in group_df["__split"].to_list()]
                        if any(split == 0 or (split > 0) != (cents > 0) for split in splits) or sum(splits) % cents != 0:
                            _bank_error(
                                file_name,
                                f"row {group_df['__row'][0]}",
                                "SPLIT_INVALID",
                                f"transaction on [{group_df['__account_name'][0]}] split parts [{', '.join(str(split / 100) for split in splits)}] do not sum to amount [{cents / 100}]",
                            )
                            file_valid = False
                        elif sum(splits) // cents > 1 and group_df["__posted"].is_null().all():
                            _bank_error(
                                file_name,
                                f"row {group_df['__row'][0]}",
                                "MANUAL_DUPLICATE",
                                f"manual transaction [{group_df['Description'][0]}] on [{group_df['__account_name'][0]}] identical to another on the same date",
                            )
                normalised_counts["files"] += 1
                if not file_valid:
                    normalised_counts["invalid"] += 1
                    years_held.add(file_year)
                    files_invalid.add(path)
                    self.print_log(f"File [{file_name}] left as is, invalid rows", level="warn")
                    continue
                for row in rows_df.filter(pl.col("Category Manual").is_not_null()).iter_rows(named=True):
                    if classifier_usable and row["Category Manual"] not in classifier_categories:
                        _bank_error(
                            file_name, f"row {row['__row']}", "CATEGORY_UNKNOWN", f"transaction on [{row['__account_name']}] category manual [{row['Category Manual']}] not on the Classifier tab"
                        )
                normalised_df = rows_df.select(
                    pl.col("__date").alias("Date"),
                    pl.col("__posted").alias("Date Posted"),
                    pl.coalesce("Account", "__account_name").alias("Account"),
                    pl.col("__value").alias("Amount"),
                    pl.coalesce("__split", "__value").alias("Amount Split"),
                    pl.col("Description"),
                    pl.col("Bank Code"),
                    pl.col("Merchant Code"),
                    pl.col("Notes"),
                    pl.col("__vetted").alias("Vetted"),
                    pl.col("Category Manual"),
                    pl.lit(None, dtype=pl.Utf8).alias("Category"),
                    pl.col("Category Auto"),
                    pl.col("__account_id").alias("Account ID"),
                    pl.col("Source ID"),
                    pl.lit(None, dtype=pl.Utf8).alias("Transaction ID"),
                )
                normalised_frames[path] = normalised_df
            for path, normalised_df in normalised_frames.items():
                file_name, file_year = basename(path), _bank_file(path)[1]
                unmovable = [
                    year
                    for year in sorted(set(normalised_df["Date"].dt.year().to_list()) - {file_year})
                    if _bank_path("manual_transactions", year) not in normalised_frames and (year in years_held or not _bank_writable(_bank_path("manual_transactions", year)))
                ]
                if unmovable:
                    _bank_error(file_name, ", ".join(str(year) for year in unmovable), "FILE_UNREADABLE", "rows dated in a year whose manual file is unreadable or invalid, left as is")
                    years_held.add(file_year)
                    files_invalid.add(path)
            for path in [path for path in normalised_frames if path in files_invalid]:
                del normalised_frames[path]
            for year in sorted({year for normalised_df in normalised_frames.values() for year in normalised_df["Date"].dt.year().to_list()} | {_bank_file(path)[1] for path in normalised_frames}):
                year_path = _bank_path("manual_transactions", year)
                year_frames = [frame_df.filter(pl.col("Date").dt.year() == year) for frame_df in normalised_frames.values()]
                if year_path not in normalised_frames and isfile(year_path):
                    year_frames.insert(0, cast(pl.DataFrame, _bank_readable(year_path, TRANSACTIONS_SCHEMA)))
                _bank_write(pl.concat([pl.DataFrame(schema=TRANSACTIONS_SCHEMA), *year_frames], how="vertical_relaxed"), year_path, "normalised")

            for path in _bank_paths("manual_balances"):
                if not _bank_changed(path) or not accounts_usable:
                    continue
                file_name = basename(path)
                try:
                    rows_df = _bank_operator_rows(path, list(BALANCES_SCHEMA))
                except Exception as exception:
                    _bank_unreadable(path, exception)
                    balances_held.add(_bank_file(path)[1])
                    continue
                rows_df = _bank_operator_accounts(
                    rows_df.with_columns(
                        _bank_operator_date("Date").alias("__date"),
                        pl.coalesce("Balance Manual", "Balance").alias("__text"),
                        pl.coalesce(_bank_operator_amount("Balance Manual"), _bank_operator_amount("Balance")).alias("__value"),
                        pl.col("Time").str.zfill(8).str.to_time("%H:%M:%S", strict=False).dt.strftime("%H:%M:%S").alias("__time"),
                    )
                ).with_columns(pl.coalesce("__time", pl.when(pl.col("Time").is_null()).then(pl.lit(BALANCES_MANUAL_TIME))).alias("__time"))
                file_valid = True
                for row in rows_df.iter_rows(named=True):
                    if not _bank_operator_checked(file_name, row):
                        file_valid = False
                    elif row["__time"] is None:
                        _bank_error(file_name, f"row {row['__row']}", "VALUE_UNPARSED", f"time [{row['Time']}] unparsed")
                        file_valid = False
                for row in rows_df.filter(pl.struct(["__date", "__time", "__account_id"]).is_duplicated() & pl.col("__account_id").is_not_null()).iter_rows(named=True):
                    _bank_error(file_name, f"row {row['__row']}", "BALANCE_DUPLICATE", f"account [{row['__account_name']}] date [{row['__date']}] time [{row['__time']}] entered twice")
                    file_valid = False
                normalised_counts["files"] += 1
                if not file_valid:
                    normalised_counts["invalid"] += 1
                    balances_held.add(_bank_file(path)[1])
                    files_invalid.add(path)
                    self.print_log(f"File [{file_name}] left as is, invalid rows", level="warn")
                    continue
                last_by_account: dict[str, float] = {}
                for row in rows_df.sort(["__date", "__time"]).iter_rows(named=True):
                    if (row["__type"] == ACCOUNT_TYPE_LIABILITY and row["__value"] > 0) or (row["__type"] != ACCOUNT_TYPE_LIABILITY and row["__value"] < 0):
                        _bank_error(file_name, f"row {row['__row']}", "BALANCE_SIGN", f"account [{row['__account_name']}] type [{row['__type']}] value [{row['__value']}]")
                    last = last_by_account.get(row["__account_id"])
                    if last not in (None, 0) and row["__value"] != 0 and not 1 / BALANCES_MANUAL_JUMP <= abs(row["__value"] / last) <= BALANCES_MANUAL_JUMP:
                        _bank_error(file_name, f"row {row['__row']}", "BALANCE_JUMP", f"account [{row['__account_name']}] value [{row['__value']}] last [{last}]")
                    last_by_account[row["__account_id"]] = row["__value"]
                _bank_write(
                    rows_df.select(
                        pl.col("__date").alias("Date"),
                        pl.col("__time").alias("Time"),
                        pl.coalesce("Account", "__account_name").alias("Account"),
                        pl.col("__value").alias("Balance"),
                        pl.col("__value").alias("Balance Manual"),
                        pl.lit(None, dtype=pl.Float64).alias("Balance Auto"),
                        pl.col("__account_id").alias("Account ID"),
                        pl.lit(None, dtype=pl.Utf8).alias("Balance ID"),
                    ),
                    path,
                    "normalised",
                )
            self.print_log(f"Files normalised [{normalised_counts['files']}] invalid [{normalised_counts['invalid']}]", started=started_time)

        _bank_manual_normalised()

        tab_edited: dict[str, set[str]] = {}
        tab_merged: set[str] = set()

        # 3.2 Merge Transactions Tabs
        def _bank_tabs_merged():
            started_time = time.time()
            merged_counts = {"edits": 0, "ignored": 0}
            edits_by_path: dict[str, dict[str, list[dict]]] = {}
            account_names = dict(_bank_accounts_current().select(["Account ID", "Name"]).iter_rows())
            for year in sheet_years:
                tab = f"Transactions_{year}"
                tab_raw_df = _bank_raw(sheet_files.get(tab))
                if tab_raw_df is None or not accounts_usable or year in years_held:
                    continue
                if tab_raw_df.height == 0:
                    tab_merged.add(tab)
                    continue
                tab_missing = [column for column in ("Transaction ID",) if column not in tab_raw_df.columns]
                if tab_missing:
                    _bank_error(tab, "tab", "TAB_UNUSABLE", f"columns missing [{', '.join(tab_missing)}]")
                    continue
                base_file = abspath(f"{self.local_cache}/__bank_tab_transactions_{year}.csv")
                if isfile(base_file):
                    base_raw_df = pl.read_csv(base_file, infer_schema=False, raise_if_empty=False)
                else:
                    base_raw_df = _bank_tab_rendered(_bank_bucketed(_bank_accounts_applied(_bank_held().filter(pl.col("Date").dt.year() == year), accounts_df))).cast(pl.Utf8)
                tab_edits, tab_ignored, tab_idless = bank_tab_edits(self.sheet_typed(tab_raw_df, TRANSACTIONS_YEAR_TAB_SCHEMA), self.sheet_typed(base_raw_df, TRANSACTIONS_YEAR_TAB_SCHEMA))
                if tab_ignored:
                    _bank_error(tab, "tab", "TAB_EDIT_IGNORED", f"[{tab_ignored}] transactions edited outside amount split, category manual, vetted and notes, put back")
                if tab_idless:
                    _bank_error(tab, "rows", "TAB_EDIT_IGNORED", f"[{tab_idless}] rows without a transaction id ignored, manual rows go in the manual files on Drive")
                merged_counts["ignored"] += tab_ignored + tab_idless
                tab_merged.add(tab)
                tab_edited[tab] = set()
                for transaction_id, edit in tab_edits.items():
                    held_df = _bank_held().filter(pl.col("Transaction ID") == transaction_id)
                    if len(held_df) == 0 and edit["Source ID"] is not None:
                        held_df = _bank_held().filter(pl.col("Source ID") == edit["Source ID"])
                    if len(held_df) == 0 and edit["Account ID"] is not None and edit["Amount"] is not None and edit["Date"] is not None:
                        candidates_df = _bank_held().filter(
                            (pl.col("Account ID") == edit["Account ID"])
                            & (bank_cents("Amount") == edit["Amount"])
                            & ((pl.col("Date") - pl.lit(edit["Date"])).dt.total_days().abs() <= TRANSACTIONS_MATCH_DAYS)
                        )
                        if candidates_df["Transaction ID"].n_unique() == 1:
                            held_df = candidates_df
                    if len(held_df) == 0 or held_df["Transaction ID"].n_unique() != 1:
                        _bank_error(tab, transaction_id, "EDIT_UNMATCHED", f"edited transaction on [{account_names.get(edit['Account ID'])}] held by no file, edit not applied")
                        continue
                    held_df = held_df.filter(pl.col("__path") == held_df["__path"][0]).sort("__index")
                    held_path = held_df["__path"][0]
                    if edit["Bad Vetted"] is not None:
                        _bank_error(tab, transaction_id, "TRANSACTION_VETTED", f"transaction on [{held_df['Account'][0]}] vetted [{edit['Bad Vetted']}] not one of [{', '.join(FLAGS)}]")
                        continue
                    held_parts = held_df.to_dicts()
                    cents = round(held_parts[0]["Amount"] * 100)
                    held_values = [
                        {
                            "Amount Split": None if part["Amount Split"] is None else round(part["Amount Split"] * 100),
                            "Category Manual": part["Category Manual"],
                            "Vetted": part["Vetted"],
                            "Notes": part["Notes"],
                        }
                        for part in held_parts
                    ]
                    if len(edit["Tab"]) == len(edit["Base"]) == len(held_parts) == 1:
                        tab_part, base_part = edit["Tab"][0], edit["Base"][0]
                        parts = [{column: tab_part[column] if column in edit["Present"] and tab_part[column] != base_part[column] else held_values[0][column] for column in TRANSACTIONS_EDIT_COLUMNS}]
                    else:
                        parts = [
                            {column: part[column] if column in edit["Present"] else held_values[min(index, len(held_values) - 1)][column] for column in TRANSACTIONS_EDIT_COLUMNS}
                            for index, part in enumerate(edit["Tab"])
                        ]
                    splits = [cents if part["Amount Split"] is None else part["Amount Split"] for part in parts]
                    if any(split == 0 or (split > 0) != (cents > 0) for split in splits) or sum(splits) != cents:
                        _bank_error(
                            tab,
                            transaction_id,
                            "SPLIT_INVALID",
                            f"transaction on [{held_parts[0]['Account']}] split parts [{', '.join(str(split / 100) for split in splits)}] do not sum to amount [{cents / 100}]",
                        )
                        continue
                    for part in parts:
                        if part["Category Manual"] is not None and classifier_usable and part["Category Manual"] not in classifier_categories:
                            _bank_error(tab, transaction_id, "CATEGORY_UNKNOWN", f"transaction on [{held_parts[0]['Account']}] category manual [{part['Category Manual']}] not on the Classifier tab")
                    edits_by_path.setdefault(held_path, {})[held_parts[0]["Transaction ID"]] = [
                        {
                            **{column: held_parts[0][column] for column in TRANSACTIONS_SCHEMA},
                            "Amount Split": split / 100,
                            "Category Manual": part["Category Manual"],
                            "Vetted": part["Vetted"],
                            "Notes": part["Notes"],
                        }
                        for part, split in zip(parts, splits, strict=True)
                    ]
                    tab_edited[tab].add(held_path)
                    merged_counts["edits"] += 1
            categories_merging_df = _bank_categories() if edits_by_path else None
            merging_df = _bank_held()
            for path, path_edits in sorted(edits_by_path.items()):
                file_df = merging_df.filter(pl.col("__path") == path)
                unidentified_df = _bank_read(path, TRANSACTIONS_SCHEMA).with_row_index("__index").join(file_df.select("__index"), on="__index", how="anti")
                replaced_frames = [
                    pl.DataFrame(path_edits[transaction_id], schema=TRANSACTIONS_SCHEMA).with_columns(pl.lit(index, dtype=pl.UInt32).alias("__index"))
                    for transaction_id, index in file_df.filter(pl.col("Transaction ID").is_in(list(path_edits))).group_by("Transaction ID", maintain_order=True).agg(pl.col("__index").min()).rows()
                ]
                _bank_write(
                    pl.concat([file_df.filter(~pl.col("Transaction ID").is_in(list(path_edits))), unidentified_df, *replaced_frames], how="diagonal_relaxed")
                    .sort("__index", maintain_order=True)
                    .select(list(TRANSACTIONS_SCHEMA)),
                    path,
                    "merged",
                )
            self.print_log(f"Sheet edits merged [{merged_counts['edits']}] ignored [{merged_counts['ignored']}] across [{len(tab_merged)}] tabs", started=started_time)
            if categories_merging_df is not None:
                _bank_categories_logged(categories_merging_df, _bank_categories(), CHANGES_SOURCE_SHEET)

        _bank_tabs_merged()

        # 3.3 Merge Balances Tab
        def _bank_balances_tab_merged():
            started_time = time.time()
            tab_raw_df = _bank_raw(sheet_files.get("Balances"))
            if tab_raw_df is None or not accounts_usable or tab_raw_df.height == 0:
                return
            tab_missing = [column for column in ("Balance ID", "Balance Manual") if column not in tab_raw_df.columns]
            if tab_missing:
                _bank_error("Balances", "tab", "TAB_UNUSABLE", f"columns missing [{', '.join(tab_missing)}]")
                return
            tab_merged.add("Balances")
            tab_edited["Balances"] = set()
            base_file = abspath(f"{self.local_cache}/__bank_tab_balances.csv")
            if not isfile(base_file):
                return
            tab_df = self.sheet_typed(tab_raw_df, BALANCES_SCHEMA)
            base_df = self.sheet_typed(pl.read_csv(base_file, infer_schema=False, raise_if_empty=False), BALANCES_SCHEMA)
            fixed = [column for column in BALANCES_SCHEMA if column not in ("Balance ID", "Balance Manual", "Balance") and column in tab_df.columns and column in base_df.columns]
            changed_df = tab_df.join(base_df.unique("Balance ID", keep="first"), on="Balance ID", suffix="__base").filter(
                pl.any_horizontal([pl.col(column).ne_missing(pl.col(f"{column}__base")) for column in [*fixed, "Balance Manual"]])
            )
            readings_df = _bank_manual_readings()
            types = dict(_bank_accounts_current().select(["Account ID", "Type"]).iter_rows())
            edits_by_path: dict[str, dict[int, float]] = {}
            ignored = 0
            for row in changed_df.iter_rows(named=True):
                reading_df = readings_df.filter(pl.col("Balance ID") == row["Balance ID"])
                if any(row[column] != row[f"{column}__base"] for column in fixed) or len(reading_df) != 1 or row["Balance Manual"] is None:
                    ignored += 1
                    continue
                reading = reading_df.row(0, named=True)
                value = row["Balance Manual"] / 100
                if (types.get(reading["Account ID"]) == ACCOUNT_TYPE_LIABILITY and value > 0) or (types.get(reading["Account ID"]) != ACCOUNT_TYPE_LIABILITY and value < 0):
                    _bank_error("Balances", row["Balance ID"], "BALANCE_SIGN", f"account [{reading['Account']}] type [{types.get(reading['Account ID'])}] value [{value}]")
                edits_by_path.setdefault(reading["__path"], {})[reading["__index"]] = value
            if ignored:
                _bank_error("Balances", "tab", "TAB_EDIT_IGNORED", f"[{ignored}] balances edited outside a manual balance's balance manual, put back")
            for path, path_edits in sorted(edits_by_path.items()):
                edited = pl.col("__index").replace_strict(path_edits, default=None, return_dtype=pl.Float64)
                _bank_write(
                    _bank_read(path, BALANCES_SCHEMA)
                    .with_row_index("__index")
                    .with_columns(pl.coalesce(edited, "Balance Manual").alias("Balance Manual"), pl.coalesce(edited, "Balance").alias("Balance"))
                    .drop("__index"),
                    path,
                    "merged",
                )
                tab_edited["Balances"].add(path)
            self.print_log(f"Balances tab edits merged [{sum(len(path_edits) for path_edits in edits_by_path.values())}] ignored [{ignored}]", started=started_time)

        _bank_balances_tab_merged()

        # 4.1 Fetch Balances
        started_time = time.time()
        balances_year_path = _bank_path("redbark_balances", today.year)
        balances_previous_year_path = _bank_path("redbark_balances", today.year - 1)
        balances_age_hours = (now.timestamp() - getmtime(balances_year_path)) / 3600 if isfile(balances_year_path) else float("inf")
        balances_due = not plugin.config.disable_source_downloads and (plugin.config.force_downloads or balances_age_hours >= BALANCES_MAX_AGE_HOURS)
        linked_schema = {"Redbark Account ID": pl.Utf8, "Redbark Connection ID": pl.Utf8, "Account ID": pl.Utf8, "From First": pl.Date, "Name": pl.Utf8, "Institution": pl.Utf8}
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
                            "Institution": account.get("institutionName"),
                        }
                        for account in _bank_accounts_fetched("no readable tab")
                        if all(_bank_redbark_key(account.get("institutionName"), account.get("accountNumber")))
                    ],
                    schema=linked_schema,
                )

            def _bank_balances_fetched(_linked_ids) -> pl.DataFrame:
                _linked_names = dict(linked_df.select(["Redbark Account ID", "Name"]).iter_rows())
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
                            _bank_error("Redbark", _account_id, "BALANCE_RESPONSE", f"balance on [{_linked_names.get(_account_id)}] unknown, duplicated or without value or observed time")
                        elif _freshness not in (None, "fresh"):
                            _bank_error("Redbark", _account_id, "BALANCE_STALE", f"balance on [{_linked_names.get(_account_id)}] freshness [{_freshness}]")
                    _readings_df = _response_df.filter("__usable").select(
                        pl.col("__observed").dt.date().alias("Date"),
                        pl.col("__observed").dt.strftime("%H:%M:%S").alias("Time"),
                        pl.col("Name").alias("Account"),
                        pl.col("__amount").alias("Balance"),
                        pl.lit(None, dtype=pl.Float64).alias("Balance Manual"),
                        pl.col("__amount").alias("Balance Auto"),
                        "Account ID",
                        pl.lit(None, dtype=pl.Utf8).alias("Balance ID"),
                    )
                    for _redbark_id in sorted(set(_linked_ids) - set(_response_df["accountId"].to_list())):
                        _bank_error("Redbark", _redbark_id, "BALANCE_ABSENT", f"linked account [{_linked_names.get(_redbark_id)}] absent from the balances response")
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
                        readings_df.join(latest_df, on="Account ID", how="left").filter(pl.col("__latest").is_null() | (bank_cents("Balance") != bank_cents("__latest"))).select(list(BALANCES_SCHEMA))
                    )
                    changed_count = len(changed_df)
                    opening = len(balances_year_df.filter(pl.col("Date") >= month_start)) == 0
                    written_df = readings_df.join(balances_year_df, on=["Date", "Time", "Account ID"], how="anti") if opening else changed_df
                    if len(written_df):
                        _bank_write(
                            pl.concat([balances_year_df, written_df], how="vertical_relaxed").unique(["Date", "Time", "Account ID"], keep="last", maintain_order=True), balances_year_path, "fetched"
                        )
                    if isfile(balances_year_path):
                        os.utime(balances_year_path, (now.timestamp(), now.timestamp()))
                    self.print_log(f"Balances [{changed_count}] changed of [{len(readings_df)}] accounts, opening [{opening}]", started=started_time)
        elif not plugin.config.disable_source_downloads and balances_year_path not in files_unreadable:
            self.add_counter(plugin.CTR_SRC_SOURCES, plugin.CTR_ACT_CACHED)
            self.print_log(f"Balances check skipped, fresh at age [{balances_age_hours:.2f}] hours", level="debug")

        # 4.2 Fetch Transactions
        def _bank_transactions_fetched_redbark():
            started_time = time.time()
            redbark_transactions_file = abspath(f"{self.local_cache}/_redbark_transactions.csv")
            sweep_file = abspath(f"{self.local_cache}/_redbark_transactions_sweep.csv")
            sweep_due = isfile(sweep_file) and (now.timestamp() - getmtime(sweep_file)) / 86400 >= TRANSACTIONS_SWEEP_EVERY_DAYS

            def _bank_named(_frame_df: pl.DataFrame) -> pl.DataFrame:
                return _bank_accounts_applied(_frame_df, accounts_df).with_columns(_bank_name("Account").alias("__name"), bank_cents("Amount").alias("__cents"))

            if balances_due and len(linked_df):
                held_frames = [pl.DataFrame(schema={"__index": pl.UInt32, **TRANSACTIONS_SCHEMA, "__path": pl.Utf8})]
                for path in _bank_paths("redbark_transactions", "manual_transactions"):
                    held_file_df = _bank_readable(path, TRANSACTIONS_SCHEMA)
                    if held_file_df is not None:
                        held_frames.append(held_file_df.with_row_index("__index").with_columns(pl.lit(path).alias("__path")))
                held_df = _bank_named(pl.concat(held_frames, how="vertical_relaxed"))
                transactions_returned_frames = [pl.DataFrame(schema=TRANSACTIONS_SCHEMA)]
                returned_ids: dict[str, set[str]] = {}
                transactions_windows: dict[str, tuple[date, date]] = {}
                held_latest = dict(held_df.filter(pl.col("__path").str.contains("redbark_transactions_")).group_by("Account ID").agg(pl.col("Date").max()).rows())

                def _bank_transactions_fetched(_accounts):
                    _paths = {}
                    for _account in _accounts:
                        _history = max(_account["From First"] or date(1, 1, 1), today - timedelta(days=TRANSACTIONS_HISTORY_DAYS))
                        _from = held_latest[_account["Account ID"]] - timedelta(days=TRANSACTIONS_LEEWAY_DAYS) if _account["Account ID"] in held_latest else _history
                        _check = max(min(_from, today - timedelta(days=TRANSACTIONS_SWEEP_DAYS)), _history) if sweep_due else _from
                        transactions_windows[_account["Account ID"]] = (_from, _check)
                        _paths[_account["Account ID"]] = (
                            f"/v1/transactions?connectionId={_account['Redbark Connection ID']}&accountId={_account['Redbark Account ID']}&from={_history if plugin.config.force_downloads else _check}"
                        )
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
                                f"Transactions window account [{_account['Account ID']}] from [{transactions_windows[_account['Account ID']][1]}] to [{today}] returned [{len(_account_rows_df)}]",
                                level="debug",
                            )
                        elif _error["Status"] == 404:
                            _dead.append(_account)
                        else:
                            _bank_error("Redbark", _account["Account ID"], "TRANSACTION_CALL", f"transactions call for [{_account['Name']}] failed [{_error['Status'] or _error['Detail']}]")
                    return _returned, _dead

                linked_accounts = list(linked_df.iter_rows(named=True))
                returned_rows, dead = _bank_transactions_fetched(linked_accounts)
                if sweep_due or not isfile(sweep_file):
                    with open(sweep_file, "a"):
                        os.utime(sweep_file, (now.timestamp(), now.timestamp()))
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
                    _bank_error("Accounts", account["Account ID"], "REDBARK_GONE", f"Redbark id [{account['Redbark Account ID']}] of [{account['Name']}] {reason}")
                transaction_valid = (
                    pl.col("__amount").is_not_null()
                    & ~pl.col("__amount").is_nan()
                    & pl.col("__made").is_not_null()
                    & pl.col("__posted").is_not_null()
                    & (pl.col("id").fill_null("") != "")
                    & ~pl.col("__duplicated")
                    & pl.col("status").is_not_null()
                )
                for account, rows_df in returned_rows:
                    returned_ids[account["Account ID"]] = set(rows_df["id"].fill_null("").to_list())
                    made_zone = REDBARK_INSTITUTION_TIMEZONES.get(account["Institution"] or "")
                    made_text = pl.col("datetime").cast(pl.Utf8).str.strip_chars().str.replace(r"Z$", "+00:00")
                    parsed_df = (
                        rows_df.with_columns(pl.col("id").fill_null("").is_duplicated().alias("__duplicated"))
                        .filter(pl.col("status").is_null() | (pl.col("status") == "posted"))
                        .with_columns(
                            pl.col("amount").cast(pl.Float64, strict=False).alias("__amount"),
                            pl.coalesce(
                                *([made_text.str.to_datetime("%Y-%m-%dT%H:%M:%S%.f%:z", time_zone="UTC", strict=False).dt.convert_time_zone(made_zone).dt.date()] if made_zone else []),
                                _bank_text("date").str.to_date("%Y-%m-%d", strict=False),
                                _bank_text("postDate").str.to_date("%Y-%m-%d", strict=False),
                            ).alias("__made"),
                            pl.coalesce(_bank_text("postDate"), _bank_text("date")).str.to_date("%Y-%m-%d", strict=False).alias("__posted"),
                            pl.col("merchantCategoryCode").fill_null("").str.strip_chars().alias("__merchant"),
                        )
                    )
                    for transaction_id in parsed_df.filter(~transaction_valid)["id"].to_list():
                        _bank_error("Redbark", transaction_id or "", "TRANSACTION_RESPONSE", "transaction without id, amount, dates or status, or duplicated")
                    transactions_returned_frames.append(
                        parsed_df.filter(transaction_valid).select(
                            [
                                pl.col("__made").alias("Date"),
                                pl.col("__posted").alias("Date Posted"),
                                pl.lit(account.get("Name"), dtype=pl.Utf8).alias("Account"),
                                pl.col("__amount").alias("Amount"),
                                pl.col("__amount").alias("Amount Split"),
                                pl.col("description").fill_null("").alias("Description"),
                                pl.col("category").replace("", None).alias("Bank Code"),
                                pl.when((pl.col("__merchant") != "") & (pl.col("__merchant") != CLASSIFIER_MERCHANT_CODE_NONE)).then(pl.col("__merchant").str.zfill(4)).alias("Merchant Code"),
                                pl.lit(account["Account ID"], dtype=pl.Utf8).alias("Account ID"),
                                pl.col("id").alias("Source ID"),
                            ]
                        )
                    )
                windows_df = pl.DataFrame(
                    [(account_id, window[0], window[1]) for account_id, window in transactions_windows.items()], schema={"Account ID": pl.Utf8, "__from": pl.Date, "__check": pl.Date}, orient="row"
                )
                transactions_new_df = (
                    _bank_named(pl.concat(transactions_returned_frames, how="diagonal_relaxed").select(list(TRANSACTIONS_SCHEMA)))
                    .join(windows_df, on="Account ID", how="left", maintain_order="left")
                    .with_columns((pl.col("Date") >= pl.col("__from")).fill_null(False).alias("__window"), (pl.col("Date") >= pl.col("__check")).fill_null(False).alias("__checked"))
                    .sort(["Date", "Source ID"])
                )
                returned_all = set().union(*returned_ids.values())
                held_windowed_df = held_df.join(windows_df, on="Account ID", how="left", maintain_order="left").with_columns(
                    (
                        pl.col("__path").str.contains("redbark_transactions_")
                        & pl.col("Source ID").is_not_null()
                        & ~pl.col("Source ID").is_in(list(returned_all))
                        & pl.col("Account ID").is_in(list(returned_ids))
                        & (pl.when(pl.col("Date Posted").is_null()).then(pl.col("Date") - timedelta(days=TRANSACTIONS_POSTING_DAYS)).otherwise(pl.col("Date")) > pl.col("__check"))
                    )
                    .fill_null(False)
                    .alias("__gone")
                )
                window_held_df = held_windowed_df.filter(pl.col("__check").is_null() | (pl.col("Date") >= pl.col("__check") - timedelta(days=TRANSACTIONS_MATCH_DAYS)))
                ambiguous: set[int] = set()

                def _bank_matched(_new_df: pl.DataFrame) -> dict[int, tuple[str, int]]:
                    _new_df = _new_df.with_row_index("__new")
                    _sourced_df = held_df.filter(pl.col("Source ID").is_not_null()).unique("Source ID", keep="first", maintain_order=True)
                    _matched = {
                        _new: (_path, _index)
                        for _new, _path, _index in _new_df.join(_sourced_df.select(["Source ID", "__path", "__index"]), on="Source ID").select(["__new", "__path", "__index"]).iter_rows()
                    }
                    _held_df = window_held_df.filter(pl.col("Source ID").is_null() | pl.col("__gone")).with_row_index("__held")
                    _held_rows = dict(zip(_held_df["__held"].to_list(), zip(_held_df["__path"].to_list(), _held_df["__index"].to_list(), strict=True), strict=True))
                    _pairs: list[pl.DataFrame] = []
                    for _priority, _keys in enumerate((["__name", "__cents"], ["Account ID", "__cents"])):
                        _pairs.append(
                            _new_df.filter(~pl.col("__new").is_in(list(_matched)) & pl.col("__checked"))
                            .select(["__new", "Date", "__window", *_keys])
                            .join(_held_df.select(["__held", pl.col("Date").alias("__held_date"), *_keys]), on=_keys)
                            .select(
                                [
                                    "__new",
                                    "__held",
                                    "__window",
                                    pl.lit(_priority).alias("__priority"),
                                    (pl.col("Date") - pl.col("__held_date")).dt.total_days().abs().alias("__distance"),
                                    pl.col("__held_date"),
                                ]
                            )
                        )
                    _pairs_df = pl.concat(_pairs).filter(pl.col("__distance") <= TRANSACTIONS_MATCH_DAYS).unique(["__new", "__held"], keep="first", maintain_order=True)
                    _inside_held = _pairs_df.filter(pl.col("__window"))["__held"].implode()
                    ambiguous.update(
                        _pairs_df.filter(~pl.col("__window")).filter((pl.len().over("__new") > 1) | (pl.len().over("__held") > 1) | pl.col("__held").is_in(_inside_held))["__new"].to_list()
                    )
                    _pairs_df = _pairs_df.filter(pl.col("__window") | ~pl.col("__new").is_in(list(ambiguous))).sort(["__new", "__priority", "__distance", "__held_date", "__held"])
                    _absorbed = set()
                    while len(_pairs_df):
                        _choice_df = (
                            _pairs_df.group_by("__new", maintain_order=True).first().sort(["__priority", "__distance", "__held_date", "__new"]).unique("__held", keep="first", maintain_order=True)
                        )
                        _matched.update({_new: _held_rows[_held] for _new, _held in zip(_choice_df["__new"].to_list(), _choice_df["__held"].to_list(), strict=True)})
                        _absorbed.update(_choice_df["__held"].to_list())
                        _pairs_df = _pairs_df.filter(~pl.col("__new").is_in(list(_matched)) & ~pl.col("__held").is_in(list(_absorbed)))
                    return _matched

                matched = _bank_matched(transactions_new_df)
                unmatched_df = transactions_new_df.with_row_index("__new").filter(~pl.col("__new").is_in(list(matched)))
                fresh_df = unmatched_df.filter(pl.col("__window")).select(list(TRANSACTIONS_SCHEMA))
                for row in unmatched_df.filter(~pl.col("__window") & pl.col("__checked")).iter_rows(named=True):
                    if row["__new"] in ambiguous:
                        _bank_error(
                            f"Transactions_{row['Date'].year}",
                            row["Source ID"],
                            "TRANSACTION_RELISTED",
                            f"transaction on [{row['Account']}] date [{row['Date']}] pairs with more than one held transaction, not adopted",
                        )
                    else:
                        _bank_error(
                            f"Transactions_{row['Date'].year}",
                            row["Source ID"],
                            "TRANSACTION_UNHELD",
                            f"transaction on [{row['Account']}] date [{row['Date']}] listed by Redbark before the add window and held by no file",
                        )
                held_rows = {(row["__path"], row["__index"]): row for row in held_df.iter_rows(named=True)}
                new_rows = transactions_new_df.to_dicts()
                updates: dict[str, dict[int, dict]] = {}
                relisted_count, dated_count = 0, 0
                for new_index, held_key in matched.items():
                    new_row, held_row = new_rows[new_index], held_rows[held_key]
                    update = {}
                    if held_row["Source ID"] != new_row["Source ID"]:
                        update["Source ID"] = new_row["Source ID"]
                        if held_row["Source ID"] is not None:
                            relisted_count += 1
                            _bank_error(
                                f"Transactions_{held_row['Date'].year}",
                                held_row["Source ID"],
                                "TRANSACTION_RELISTED",
                                f"held transaction [{(held_row['Description'] or '').strip()}] on [{held_row['Account']}] date [{held_row['Date']}] relisted by Redbark as [{new_row['Source ID']}]",
                            )
                    if held_row["Date Posted"] is None and (new_row["Date"].year == held_row["Date"].year or _bank_writable(_bank_path(_bank_file(held_key[0])[0], new_row["Date"].year))):
                        update.update({"Date": new_row["Date"], "Date Posted": new_row["Date Posted"]})
                        dated_count += 1
                    if update:
                        updates.setdefault(held_key[0], {})[held_key[1]] = update
                moved_rows: dict[str, list[pl.DataFrame]] = {}
                for path, path_updates in sorted(updates.items()):
                    family, year = _bank_file(path)
                    updated_df = _bank_read(path, TRANSACTIONS_SCHEMA).with_row_index("__index")
                    for column in ("Source ID", "Date", "Date Posted"):
                        values = {index: update[column] for index, update in path_updates.items() if column in update}
                        if values:
                            updated_df = updated_df.with_columns(
                                pl.coalesce(pl.col("__index").replace_strict(values, default=None, return_dtype=TRANSACTIONS_SCHEMA[column]), pl.col(column)).alias(column)
                            )
                    updated_df = updated_df.drop("__index")
                    for (moved_year,), moved_df in (
                        updated_df.filter(pl.col("Date").dt.year() != year).with_columns(pl.col("Date").dt.year().alias("__year")).partition_by("__year", as_dict=True, include_key=False).items()
                    ):
                        moved_rows.setdefault(_bank_path(family, moved_year), []).append(moved_df)
                    _bank_write(updated_df.filter(pl.col("Date").dt.year() == year), path, "adopted")
                    self.print_log(f"Held transactions updated [{len(path_updates)}] from Redbark in [{basename(path)}]", level="debug")
                for path, frames in sorted(moved_rows.items()):
                    prior_df = _bank_read(path, TRANSACTIONS_SCHEMA) if isfile(path) else pl.DataFrame(schema=TRANSACTIONS_SCHEMA)
                    _bank_write(pl.concat([prior_df, *frames], how="vertical_relaxed"), path, "adopted")
                matched_held = set(matched.values())
                for row in held_windowed_df.filter(pl.col("__gone")).iter_rows(named=True):
                    if (row["__path"], row["__index"]) not in matched_held:
                        _bank_error(
                            f"Transactions_{row['Date'].year}",
                            row["Source ID"],
                            "TRANSACTION_GONE",
                            f"held transaction [{(row['Description'] or '').strip()}] on [{row['Account']}] date [{row['Date']}]"
                            + (f" posted [{row['Date Posted']}]" if row["Date Posted"] is not None else "")
                            + f" window from [{row['__check']}] no longer listed by Redbark",
                        )
                for year in sorted(set(fresh_df["Date"].dt.year().to_list())):
                    year_path = _bank_path("redbark_transactions", year)
                    if year_path in files_unreadable:
                        continue
                    prior_df = _bank_read(year_path, TRANSACTIONS_SCHEMA) if isfile(year_path) else pl.DataFrame(schema=TRANSACTIONS_SCHEMA)
                    _bank_write(pl.concat([prior_df, fresh_df.filter(pl.col("Date").dt.year() == year)], how="vertical_relaxed"), year_path, "fetched")
                self.print_log(
                    f"Transactions fetched [{len(transactions_new_df)}] across [{len(returned_rows)}] accounts, sweep [{sweep_due}], "
                    f"new [{len(fresh_df)}] held [{len(matched)}] relisted [{relisted_count}] dated [{dated_count}]",
                    started=started_time,
                )

        _bank_transactions_fetched_redbark()

        exports: dict[str, tuple[pl.DataFrame, str | None]] = {}
        exports_md5: dict[str, str] = {}
        exports_imported: set[str] = set()

        # 4.3 Import Exports
        def _bank_exports_imported():
            started_time = time.time()
            exports_accounts_df = accounts_current_df.filter(pl.col("Institution").str.contains(EXPORT_INSTITUTION_PATTERN))
            exports_numbers = {str(number).lower(): account_id for account_id, number in exports_accounts_df.select(["Account ID", "Number"]).iter_rows() if number is not None}

            def _bank_date_valid(_text: str) -> bool:
                try:
                    date.fromisoformat(_text)
                    return True
                except ValueError:
                    return False

            for path in sorted(abspath(path).lower() for path in glob.glob(f"{self.local_cache}/*.csv")):
                name = basename(path)
                if not re.fullmatch(EXPORT_NEW_PATTERN, name) and not re.fullmatch(EXPORT_NAME_PATTERN, name):
                    continue
                try:
                    with open(path, "rb") as export_handle:
                        export_df, export_pending = bank_export_parsed(export_handle.read())
                except Exception as exception:
                    _bank_error(name, "file", "IMPORT_UNREADABLE", f"export unreadable [{exception}], fix or replace it")
                    continue
                name_match = re.fullmatch(EXPORT_NAME_PATTERN, name)
                exports_md5[path] = self._file_md5(path)
                exports[path] = (export_df, exports_numbers.get(name_match[1]) if name_match is not None and _bank_date_valid(name_match[2]) else None)
                if export_pending:
                    self.print_log(f"File [{name}] skipped [{export_pending}] pending rows", level="debug")
            cards_known = {card: account_id for export_df, account_id in exports.values() if account_id is not None for card in export_df["Card"].drop_nulls().unique().to_list()}
            for path, (export_df, account_id) in list(exports.items()):
                if account_id is not None:
                    continue
                del exports[path]
                if (
                    drive_folder is not None
                    and not plugin.config.disable_drive_downloads
                    and basename(path) not in self.drive_ids
                    and any(exports_md5[path] == exports_md5[other] for other, (_, other_id) in exports.items() if other_id is not None)
                ):
                    self.print_log(f"File [{basename(path)}] skipped, a stale copy of an export renamed on Drive", level="warn")
                    continue
                account_id, reason = bank_export_account(export_df, cards_known, exports_accounts_df.select("Account ID"), _bank_held().select(["Account ID", "Date", "Amount", "Description"]))
                if account_id is None:
                    _bank_error(basename(path), "file", "IMPORT_UNMAPPED", f"export maps to no one account [{reason}], rename it amex_<number>_transactions_<date>.csv")
                    continue
                stem = f"amex_{exports_accounts_df.filter(pl.col('Account ID') == account_id)['Number'][0].lower()}_transactions_{export_df['Date'].max() or today}"
                renamed, suffix = f"{stem}.csv", 1
                while isfile(join(self.local_cache, renamed)):
                    suffix += 1
                    renamed = f"{stem}_{suffix}.csv"
                if self.drive_rename(drive_folder, self.local_cache, basename(path), renamed):
                    renamed_path = abspath(join(self.local_cache, renamed)).lower()
                    exports[renamed_path] = (export_df, account_id)
                    exports_md5[renamed_path] = exports_md5.pop(path)
                    cards_known.update(dict.fromkeys(export_df["Card"].drop_nulls().unique().to_list(), account_id))
            exports_status = dict(exports_accounts_df.select(["Account ID", "Status"]).iter_rows())
            for path, (_, account_id) in list(exports.items()):
                if exports_status.get(account_id) not in (ACCOUNT_STATUS_MANUAL, ACCOUNT_STATUS_CLOSED):
                    _bank_error(basename(path), "file", "ACCOUNT_LINKED", f"export of account [{account_id}] not Manual or Closed, not imported")
                    del exports[path]
            exports_counts = {"added": 0, "held": 0, "dated": 0}
            exports_listed: dict[tuple, int] = {}
            exports_spans: dict[str, list[tuple[date, date]]] = {}
            for path, (export_df, account_id) in exports.items():
                keys_df = export_df.with_columns(bank_cents("Amount").alias("__cents"), bank_canonical("Description").alias("__description")).with_columns(
                    pl.int_range(pl.len()).over(["Date", "__cents", "__description"]).alias("__ordinal")
                )
                for day, cents, description, count in keys_df.group_by(["Date", "__cents", "__description"]).len().iter_rows():
                    exports_listed[(account_id, day, cents, description)] = max(exports_listed.get((account_id, day, cents, description), 0), count)
                if len(export_df):
                    exports_spans.setdefault(cast(str, account_id), []).append((cast(date, export_df["Date"].min()), cast(date, export_df["Date"].max())))
                if not plugin.config.force_downloads and (plugin.config.force_reprocessing or files_committed.get(basename(path)) == exports_md5[path]):
                    continue
                exports_imported.add(path)
                file_counts = {"added": 0, "held": 0}
                for year in sorted(set(keys_df["Date"].dt.year().to_list())):
                    year_df = _bank_year_frame(year)
                    manual_path = _bank_path("manual_transactions", year)
                    if year_df is None or not _bank_writable(manual_path):
                        _bank_error(basename(path), str(year), "FILE_UNREADABLE", f"year [{year}] has an unreadable file, export rows not imported")
                        continue
                    held_ordinals_df = (
                        year_df.filter((pl.col("Account ID") == account_id) & pl.col("Transaction ID").is_not_null())
                        .unique("Transaction ID", keep="first", maintain_order=True)
                        .with_columns(bank_cents("Amount").alias("__cents"), bank_canonical("Description").alias("__description"))
                        .with_columns(pl.int_range(pl.len()).over(["Date", "__cents", "__description"]).alias("__ordinal"))
                        .select(["Transaction ID", "Date", "__cents", "__description", "__ordinal", pl.col("Date Posted").alias("__held_posted"), "__path"])
                    )
                    export_year_df = keys_df.filter(pl.col("Date").dt.year() == year).join(held_ordinals_df, on=["Date", "__cents", "__description", "__ordinal"], how="left")
                    added_df = export_year_df.filter(pl.col("Transaction ID").is_null())
                    file_counts["held"] += len(export_year_df) - len(added_df)
                    for (dated_path,), dated_path_df in export_year_df.filter(pl.col("Transaction ID").is_not_null() & pl.col("__held_posted").is_null()).partition_by("__path", as_dict=True).items():
                        dated = dict(dated_path_df.select(["Transaction ID", "Date Posted"]).iter_rows())
                        _bank_write(
                            year_df.filter(pl.col("__path") == dated_path)
                            .sort("__index")
                            .with_columns(pl.coalesce("Date Posted", pl.col("Transaction ID").replace_strict(dated, default=None, return_dtype=pl.Date)).alias("Date Posted"))
                            .select(list(TRANSACTIONS_SCHEMA)),
                            str(dated_path),
                            "dated",
                        )
                        exports_counts["dated"] += len(dated)
                    if len(added_df):
                        _bank_write(
                            pl.concat(
                                [
                                    _bank_read(manual_path, TRANSACTIONS_SCHEMA) if isfile(manual_path) else pl.DataFrame(schema=TRANSACTIONS_SCHEMA),
                                    added_df.select(
                                        pl.col("Date"),
                                        pl.col("Date Posted"),
                                        pl.lit(exports_accounts_df.filter(pl.col("Account ID") == account_id)["Name"][0], dtype=pl.Utf8).alias("Account"),
                                        pl.col("Amount"),
                                        pl.col("Amount").alias("Amount Split"),
                                        pl.col("Description"),
                                        pl.lit(account_id, dtype=pl.Utf8).alias("Account ID"),
                                    ),
                                ],
                                how="diagonal_relaxed",
                            ),
                            manual_path,
                            "imported",
                        )
                        file_counts["added"] += len(added_df)
                exports_counts["added"] += file_counts["added"]
                exports_counts["held"] += file_counts["held"]
                self.print_log(f"File [{basename(path)}] imported [{len(export_df)}] added [{file_counts['added']}] held [{file_counts['held']}]")
            carried_rows = []
            carried_path = _bank_path("manual_balances", today.year)
            carried_ids = sorted(
                {account_id for path, (_, account_id) in exports.items() if account_id is not None and path in exports_imported and exports_status.get(account_id) == ACCOUNT_STATUS_MANUAL}
            )
            if carried_ids and isfile(carried_path) and _bank_readable(carried_path, BALANCES_SCHEMA) is None:
                _bank_error(basename(carried_path), "file", "FILE_UNREADABLE", "balances file unreadable or invalid, no balance carried to today")
            elif carried_ids:
                readings_df = _bank_manual_readings().filter(pl.col("Balance Manual").is_not_null()).sort(["Date", "Time"])
                for account_id in carried_ids:
                    account_readings_df = readings_df.filter(pl.col("Account ID") == account_id)
                    if len(account_readings_df.filter(pl.col("Date") >= today)) == 0:
                        carried = account_readings_df["Balance Manual"][-1] if len(account_readings_df) else 0.0
                        carried_rows.append(
                            {
                                "Date": today,
                                "Time": BALANCES_MANUAL_TIME,
                                "Account": exports_accounts_df.filter(pl.col("Account ID") == account_id)["Name"][0],
                                "Balance": carried,
                                "Balance Manual": carried,
                                "Account ID": account_id,
                            }
                        )
                if carried_rows:
                    _bank_write(
                        pl.concat(
                            [_bank_read(carried_path, BALANCES_SCHEMA) if isfile(carried_path) else pl.DataFrame(schema=BALANCES_SCHEMA), pl.DataFrame(carried_rows, schema=BALANCES_SCHEMA)],
                            how="vertical_relaxed",
                        ),
                        carried_path,
                        "carried",
                    )
            for account_id, spans in exports_spans.items():
                account_df = (
                    _bank_held()
                    .filter(pl.col("Account ID") == account_id)
                    .unique("Transaction ID", keep="first", maintain_order=True)
                    .with_columns(bank_cents("Amount").alias("__cents"), bank_canonical("Description").alias("__description"))
                    .with_columns(pl.int_range(pl.len()).over(["Date", "__cents", "__description"]).alias("__ordinal"))
                )
                account_df = account_df.with_columns(
                    pl.Series(
                        "__listed",
                        [
                            ordinal < exports_listed.get((account_id, day, cents, description), 0)
                            for day, cents, description, ordinal in account_df.select(["Date", "__cents", "__description", "__ordinal"]).iter_rows()
                        ],
                        dtype=pl.Boolean,
                    )
                )
                unlisted_df = account_df.filter(~pl.col("__listed") & pl.any_horizontal([(pl.col("Date") > first) & (pl.col("Date") < last) for first, last in spans]))
                for row in unlisted_df.iter_rows(named=True):
                    _bank_error(
                        f"Transactions_{row['Date'].year}",
                        row["Transaction ID"],
                        "IMPORT_GONE",
                        f"held transaction on [{row['Account']}] date [{row['Date']}] inside an export's dates listed by no export",
                    )
                for row in (
                    unlisted_df.join(account_df.filter(pl.col("__listed")).select(["__cents", "Date", "Transaction ID"]), on="__cents", suffix="_listed")
                    .filter((pl.col("Date") - pl.col("Date_listed")).dt.total_days().abs() <= TRANSACTIONS_MATCH_DAYS)
                    .unique("Transaction ID", keep="first", maintain_order=True)
                    .iter_rows(named=True)
                ):
                    _bank_error(
                        f"Transactions_{row['Date'].year}",
                        row["Transaction ID"],
                        "IMPORT_SUSPECT",
                        f"held transaction on [{row['Account']}] date [{row['Date']}] near exported transaction [{row['Transaction ID_listed']}] of the same amount",
                    )
            self.print_log(
                f"Exports [{len(exports)}] imported [{len(exports_imported)}] added [{exports_counts['added']}] held [{exports_counts['held']}] dated [{exports_counts['dated']}] "
                f"balances carried [{len(carried_rows)}]",
                started=started_time,
            )

        _bank_exports_imported()

        # 4.4 Dedupe Transactions
        started_time = time.time()
        dedupe_paths = _bank_paths("redbark_transactions", "manual_transactions")
        dedupe_count = 0
        if any(_bank_changed(path) for path in dedupe_paths):
            dedupe_frames = [
                bank_transactions_identified(data_df).with_row_index("__index").with_columns(pl.lit(path).alias("__path"))
                for path in dedupe_paths
                if (data_df := _bank_readable(path, TRANSACTIONS_SCHEMA)) is not None
            ]
            if dedupe_frames:
                dedupe_df = (
                    pl.concat(dedupe_frames, how="vertical_relaxed")
                    .filter(pl.col("Transaction ID").is_not_null())
                    .with_columns(pl.concat_str([pl.col("__path"), pl.col("Transaction ID")], separator="/").alias("__transaction"))
                )
                exact_df = dedupe_df.group_by("__transaction", maintain_order=True).first().filter(pl.col("Source ID").is_not_null() & ~pl.col("Source ID").is_first_distinct())
                removed = exact_df["__transaction"].implode()
                dedupe_count = len(exact_df)
                for row in exact_df.iter_rows(named=True):
                    _bank_error(
                        f"Transactions_{row['Date'].year}",
                        row["Source ID"] or row["Transaction ID"],
                        "DEDUPE_REMOVED",
                        f"duplicate transaction [{row['Description']}] on [{row['Account']}] date [{row['Date']}] removed from [{basename(row['__path'])}]",
                    )
                for path in sorted(set(exact_df["__path"].to_list())):
                    _bank_write(
                        _bank_read(path, TRANSACTIONS_SCHEMA)
                        .with_row_index("__index")
                        .join(dedupe_df.filter((pl.col("__path") == path) & pl.col("__transaction").is_in(removed)).select("__index"), on="__index", how="anti", maintain_order="left")
                        .drop("__index"),
                        path,
                        "deduped",
                    )
        self.print_log(f"Dedupe removed [{dedupe_count}] by source id", started=started_time)

        # 5.1 Classify Transactions
        def _bank_transactions_classified():
            started_time = time.time()
            classify_all = plugin.config.force_reprocessing or classifier_content_changed
            classify_frames = {path: data_df for path in dedupe_paths if (classify_all or _bank_changed(path)) and (data_df := _bank_readable(path, TRANSACTIONS_SCHEMA)) is not None}
            classify_df = pl.concat(
                [
                    pl.DataFrame(schema={"__index": pl.UInt32, **TRANSACTIONS_SCHEMA, "__path": pl.Utf8}),
                    *(frame_df.with_row_index("__index").with_columns(pl.lit(path).alias("__path")) for path, frame_df in classify_frames.items()),
                ],
                how="vertical_relaxed",
            ).with_columns(_bank_name("Description").fill_null("").alias("__description"))

            def _bank_derived(_matchers: tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]) -> tuple[pl.DataFrame, list[tuple[str, str, str, str]]]:
                _patterns_df, _bank_df, _merchant_df = _matchers
                _problems: list[tuple[str, str, str, str]] = []
                _patterns = _patterns_df["__pattern"].unique().to_list()
                _matched_df = pl.DataFrame(schema={"__description": pl.Utf8, "__pattern_category": pl.Utf8})
                if _patterns and len(classify_df):
                    _found_df = (
                        classify_df.select("__description")
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
                    if classify_all:
                        _shares_df = (
                            classify_df.select("__description")
                            .join(_found_df.select(["__description", "__pattern"]).unique(), on="__description")
                            .group_by("__pattern")
                            .len()
                            .filter(pl.col("len") > CLASSIFIER_MATCH_SHARE * max(len(classify_df), 1))
                        )
                        for _pattern, _count in _shares_df.iter_rows():
                            _problems.append(("Classifier", _pattern, "CLASSIFIER_SHARE", f"pattern matches [{_count}] transactions, over the share"))
                return (
                    classify_df.join(_matched_df, on="__description", how="left")
                    .join(_merchant_df, on="Merchant Code", how="left")
                    .join(_bank_df, on="Bank Code", how="left")
                    .with_columns(pl.coalesce("__pattern_category", "__merchant", "__bank").alias("__derived"))
                ), _problems

            classifier_held = classifier_holding
            derived_df = None
            if classifier_usable:
                derived_df, problems = _bank_derived((classifier_patterns_df, classifier_bank_df, classifier_merchant_df))
                for problem in problems:
                    _bank_error(*problem)
                classifier_held = classifier_held or (classifier_content_changed and len(problems) > 0)
            if classifier_held:
                _bank_error("Classifier", "tab", "CLASSIFIER_HELD", "edit held until the tab's errors are fixed, classifying with the last applied tab")
                derived_df = None
            if derived_df is None and classifier_snapshot_df is not None:
                derived_df, _ = _bank_derived(_bank_matchers(classifier_snapshot_df, False))
            categories_classifying_df = _bank_categories() if derived_df is not None and classify_frames else None
            moved_count, cleared_count = 0, 0
            if derived_df is None:
                self.print_log(f"Classified [0] of [{len(classify_df)}] rows, no usable classifier", started=started_time)
            else:
                moved = pl.coalesce("Category Manual", "__derived").ne_missing(pl.coalesce("Category Manual", "Category Auto"))
                for path, frame_df in classify_frames.items():
                    classified_df = (
                        frame_df.with_row_index("__index")
                        .join(derived_df.filter(pl.col("__path") == path).select(["__index", "__derived"]), on="__index", how="left", maintain_order="left")
                        .with_columns(moved.alias("__moved"), (moved & (bank_flag("Vetted") == FLAG_YES)).fill_null(False).alias("__cleared"))
                    )
                    moved_count += int(classified_df["__moved"].sum())
                    cleared_count += int(classified_df["__cleared"].sum())
                    classified_df = classified_df.with_columns(
                        pl.when(pl.col("__cleared")).then(pl.lit(None, dtype=pl.Utf8)).otherwise(pl.col("Vetted")).alias("Vetted"), pl.col("__derived").alias("Category Auto")
                    ).drop(["__index", "__derived", "__moved", "__cleared"])
                    if not classified_df.equals(frame_df):
                        _bank_write(classified_df, path, "classified")
                self.print_log(
                    f"Classified [{derived_df['__derived'].is_not_null().sum()}] of [{len(classify_df)}] rows with the [{'last applied' if classifier_held or not classifier_usable else 'live'}] tab, "
                    f"moved [{moved_count}] ticks cleared [{cleared_count}]",
                    started=started_time,
                )
            if categories_classifying_df is not None and cleared_count:
                _bank_categories_logged(categories_classifying_df, _bank_categories(), CHANGES_SOURCE_CLASSIFIER)
            return classifier_held

        classifier_held = _bank_transactions_classified()

        # 5.2 Format Files
        started_time = time.time()
        formatted_count = 0
        if plugin.config.force_reprocessing:
            for path in _bank_paths("redbark_balances", "manual_balances", "redbark_transactions", "manual_transactions"):
                if _bank_file(path)[1] in years_held or (data_df := _bank_readable(path, BALANCES_SCHEMA if _bank_file(path)[0].endswith("_balances") else TRANSACTIONS_SCHEMA)) is None:
                    continue
                if data_df["Account ID"].null_count() or data_df["Date"].null_count():
                    continue
                with open(path, encoding="utf-8", newline="") as handle:
                    if handle.read() == _bank_rendered(data_df, path).write_csv(line_terminator="\n", float_precision=AMOUNT_DECIMALS):
                        continue
                _bank_write(data_df, path, "formatted")
                formatted_count += 1
        self.print_log(f"Files formatted [{formatted_count}]", started=started_time)

        def _bank_collected(_file_path: str, _schema: dict) -> pl.DataFrame | None:
            if _file_path in files_unreadable or _file_path in files_invalid:
                return None
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

        accounts_changed = accounts_usable and (accounts_snapshot_df is None or not accounts_snapshot_df.equals(accounts_df.select(list(ACCOUNTS_SCHEMA))))
        balances_current_file = abspath(f"{self.local_cache}/__bank_balances_current.csv")
        transactions_current_file = abspath(f"{self.local_cache}/__bank_transactions_current.csv")
        balances_paths = _bank_paths("redbark_balances", "manual_balances")
        transactions_paths = _bank_paths("redbark_transactions", "manual_transactions")
        balances_rebuild = plugin.config.force_reprocessing or accounts_changed or not isfile(balances_current_file)
        balances_years = sorted({_bank_file(path)[1] for path in balances_paths if balances_rebuild or _bank_changed(path)})
        transactions_stale = isfile(transactions_current_file) and set(pl.read_csv(transactions_current_file, n_rows=0, raise_if_empty=False).columns) != set(TRANSACTIONS_STATE_SCHEMA)
        transactions_rebuild = plugin.config.force_reprocessing or accounts_changed or classifier_changed or transactions_stale or not isfile(transactions_current_file)
        transactions_years = sorted({_bank_file(path)[1] for path in transactions_paths if transactions_rebuild or _bank_changed(path)})
        balances_df = pl.DataFrame(schema=BALANCES_STATE_SCHEMA)
        balances_committed: list[int] = []
        transactions_committed: list[int] = []
        balances_delta_df = pl.DataFrame(schema=BALANCES_STATE_SCHEMA)
        transactions_delta_df = pl.DataFrame(schema=TRANSACTIONS_STATE_SCHEMA)
        committed = True
        try:

            def _balances_aggregate_function(_data_df):
                return _data_df.select(list(BALANCES_STATE_SCHEMA)).with_columns(cs.float().round(2))

            def _transactions_aggregate_function(_data_df):
                return _data_df.select(list(TRANSACTIONS_STATE_SCHEMA)).with_columns(cs.float().round(2))

            # 6.1 Commit Balances
            def _bank_balances_carried(_balances_df: pl.DataFrame) -> pl.DataFrame:
                _manual_ids = _bank_accounts_current().filter(pl.col("Status") == ACCOUNT_STATUS_MANUAL)["Account ID"]
                _at = pl.col("Date").dt.combine(pl.col("Time").str.zfill(8).str.to_time("%H:%M:%S", strict=False))
                _manual_df = (
                    _balances_df.filter(pl.col("Balance Manual").is_not_null() & pl.col("Account ID").is_in(_manual_ids.implode()))
                    .select(["Account ID", "Account", "Balance Manual", _at.alias("__at")])
                    .drop_nulls("__at")
                    .sort("__at")
                )
                _moments_df = _balances_df.filter(pl.col("Balance Auto").is_not_null()).select(["Date", pl.col("Time").str.zfill(8)]).unique()
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
                            pl.lit(None, dtype=pl.Float64).alias("Balance Auto"),
                            pl.col("Account ID"),
                            pl.lit(None, dtype=pl.Utf8).alias("Balance ID"),
                        ]
                    )
                    .sort(["Date", "Time", "Account ID"])
                )

            started_time = time.time()
            balances_read = {path: _bank_collected(path, BALANCES_SCHEMA) if _bank_file(path)[1] in balances_years else _bank_readable(path, BALANCES_SCHEMA) for path in balances_paths}
            for path, file_df in balances_read.items():
                if file_df is None:
                    balances_held.add(_bank_file(path)[1])
            balances_committed = [year for year in balances_years if year not in balances_held]
            if balances_committed:
                balances_read_df = pl.concat([pl.DataFrame(schema=BALANCES_SCHEMA), *(file_df for file_df in balances_read.values() if file_df is not None)], how="vertical_relaxed").with_columns(
                    pl.col("Time").str.zfill(8)
                )
                balances_df = bank_balances_identified(
                    pl.concat([balances_read_df, _bank_balances_carried(balances_read_df)], how="vertical_relaxed")
                    .with_columns(pl.coalesce("Balance Manual", "Balance Auto").alias("Balance"))
                    .unique(BALANCES_KEY_COLUMNS, keep="first", maintain_order=True)
                    .filter(pl.col("Date").dt.year().is_in(balances_committed))
                )
                balances_df = _bank_accounts_applied(balances_df, accounts_df).select(list(BALANCES_STATE_SCHEMA)).sort(BALANCES_KEY_COLUMNS)
                balances_delta_df, _, _ = self.state_cache(
                    balances_df,
                    _balances_aggregate_function,
                    key_columns=BALANCES_KEY_COLUMNS,
                    name="bank_balances",
                    replace=pl.col("Date").dt.year().is_in(balances_committed) if isfile(balances_current_file) and not plugin.config.force_reprocessing else None,
                )
                if not isfile(balances_current_file):
                    self.csv_write(pl.DataFrame(schema=BALANCES_STATE_SCHEMA), balances_current_file, print_rows=0)
            for year in sorted(balances_held & set(balances_years)):
                self.print_log(f"Balances [{year}] left as committed, a file of the year unreadable or invalid", level="warn")
            self.print_log(f"DataFrame [Balances] committed years [{', '.join(str(year) for year in balances_committed)}] with [{len(balances_df)}] rows", started=started_time)

            # 6.2 Commit Transactions
            started_time = time.time()
            transactions_frames = [pl.DataFrame(schema=TRANSACTIONS_STATE_SCHEMA)]
            for year in transactions_years:
                year_paths = [path for path in (_bank_path("redbark_transactions", year), _bank_path("manual_transactions", year)) if isfile(path)]
                if year in years_held or any(_bank_collected(path, TRANSACTIONS_SCHEMA) is None for path in year_paths) or (year_df := _bank_year_frame(year)) is None:
                    years_held.add(year)
                    self.print_log(f"Year [{year}] left as committed, a file of it unreadable or invalid", level="warn")
                    continue
                transactions_committed.append(year)
                transactions_frames.append(_bank_bucketed(_bank_accounts_applied(year_df.filter(pl.col("Transaction ID").is_not_null()), accounts_df)).select(list(TRANSACTIONS_STATE_SCHEMA)))
            for path in transactions_paths:
                if _bank_file(path)[1] not in transactions_years:
                    self.add_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_SKIPPED)
            transactions_df = pl.concat(transactions_frames, how="vertical_relaxed").sort(TRANSACTIONS_KEY_COLUMNS)
            if transactions_committed:
                transactions_partitioned = isfile(transactions_current_file) and not transactions_stale and not plugin.config.force_reprocessing
                transactions_delta_df, _, _ = self.state_cache(
                    transactions_df,
                    _transactions_aggregate_function,
                    key_columns=TRANSACTIONS_KEY_COLUMNS,
                    rebuild=transactions_stale,
                    name="bank_transactions",
                    replace=pl.col("Date").dt.year().is_in(transactions_committed) if transactions_partitioned else None,
                )
                if not isfile(transactions_current_file):
                    self.csv_write(pl.DataFrame(schema=TRANSACTIONS_STATE_SCHEMA), transactions_current_file, print_rows=0)
            self.print_log(f"DataFrame [Transactions] committed years [{', '.join(str(year) for year in transactions_committed)}] with [{len(transactions_df)}] rows", started=started_time)
        except Exception as exception:
            committed = False
            self.print_log("Unexpected error processing bank data", exception=exception)
            self.counters_set_all_errored(plugin.CTR_SRC_FILES)

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

        # 7.1 Check Accounts
        started_time = time.time()
        checked_errors = len(errors)
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
                .select(["Date", "Account", "Account ID", "Transaction ID", bank_cents("Amount").alias("__cents"), _bank_name("Description").fill_null("").alias("__description")])
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
            manual_accounts_df = _bank_accounts_current().filter(pl.col("Status") == ACCOUNT_STATUS_MANUAL).select(["Account ID", "Name"])
            manual_readings_df = (
                _bank_manual_readings()
                .filter(pl.col("Balance Manual").is_not_null())
                .drop("Account")
                .join(manual_accounts_df.rename({"Name": "Account"}), on="Account ID")
                .with_columns(pl.col("Balance Manual").alias("__balance"), pl.lit(True).alias("__manual"))
            )
            for account_id, name in manual_accounts_df.sort("Account ID").iter_rows():
                months = set(manual_readings_df.filter(pl.col("Account ID") == account_id)["Date"].dt.truncate("1mo").to_list())
                if not months:
                    _bank_error("Balances", name, "BALANCE_MANUAL_STALE", f"manual account [{name}] has no reading")
                    continue
                month = min(months)
                while month < month_start:
                    if month not in months:
                        _bank_error("Balances", f"{name} {month:%Y-%m}", "BALANCE_MANUAL_STALE", f"manual account [{name}] has no reading in closed month [{month:%Y-%m}]")
                    month = (month + timedelta(days=32)).replace(day=1)
            reconcile_ids = _bank_accounts_current().filter(pl.col("Status") == ACCOUNT_STATUS_LINKED)["Account ID"].implode()
            reconcile_readings_df = pl.concat(
                [
                    balances_current_df.filter(
                        pl.col("Balance Auto").is_not_null()
                        & pl.col("Account ID").is_in(reconcile_ids)
                        & pl.col("Date").is_between(today - timedelta(days=BALANCES_RECONCILE_DAYS), today - timedelta(days=BALANCES_RECONCILE_SETTLE_DAYS))
                    ).with_columns(pl.col("Balance Auto").alias("__balance"), pl.lit(False).alias("__manual")),
                    manual_readings_df.filter(pl.col("Account ID").is_in(transactions_current_df["Account ID"].implode())),
                ],
                how="diagonal_relaxed",
            ).sort(["Date", "Time"])
            reconcile_postings_df = transactions_current_df.select(["Account ID", "Date", pl.coalesce("Date Posted", "Date").alias("__posted"), bank_cents("Amount Split").alias("__cents")])
            for (account_id,), account_readings_df in reconcile_readings_df.partition_by("Account ID", as_dict=True, maintain_order=True).items():
                account_postings_df = reconcile_postings_df.filter(pl.col("Account ID") == account_id)
                explained_before, reading_before = None, None
                for reading in account_readings_df.iter_rows(named=True):
                    day = reading["Date"]
                    in_flight = account_postings_df.filter((pl.col("Date") <= day) & (pl.col("__posted") >= day))["__cents"].to_list()
                    in_flight_sums = {0: 0}
                    for cents in in_flight if len(in_flight) <= BALANCES_RECONCILE_IN_FLIGHT else [sum(in_flight)]:
                        for total, count in list(in_flight_sums.items()):
                            in_flight_sums[total + cents] = min(in_flight_sums.get(total + cents, count + 1), count + 1)
                    applied = account_postings_df.filter(pl.col("__posted") < day)["__cents"].sum()
                    explained = {round(reading["__balance"] * 100) - applied - total: count for total, count in in_flight_sums.items()}
                    if explained_before is not None and reading_before is not None and not explained.keys() & explained_before:
                        after, before = min(((after, before) for after in explained for before in explained_before), key=lambda pair: (explained[pair[0]], abs(pair[0] - pair[1])))
                        _bank_error(
                            "Balances",
                            f"{reading['Account']} {day}",
                            "BALANCE_UNRECONCILED_CURRENT" if reading["__manual"] and day >= month_start else "BALANCE_UNRECONCILED",
                            f"balance on [{reading['Account']}] [{reading_before['__balance']}] at [{reading_before['Date']} {reading_before['Time']}] to [{reading['__balance']}] at [{day} {reading['Time']}] "
                            f"moved [{(after - before) / 100}] more than held transactions explain, fewest in flight assumed",
                        )
                        explained_before = set(explained)
                    else:
                        explained_before = set(explained) if explained_before is None else explained.keys() & explained_before
                    reading_before = reading
        self.print_log(f"Accounts checked with [{len(errors) - checked_errors}] problems", started=started_time)

        # 7.2 Check Transactions
        started_time = time.time()
        if len(classifier_df):
            for category in sorted(set(transactions_current_df.filter(pl.col("Category").is_not_null() & pl.col("Bucket").is_null())["Category"].to_list())):
                _bank_error("Classifier", category, "CLASSIFIER_UNBUCKETED", "category in use but not on the Classifier tab")
        for column in TRANSACTIONS_SPREADSHEET_ERROR_COLUMNS:
            for row in (
                transactions_current_df.filter(pl.col(column).str.contains(TRANSACTIONS_SPREADSHEET_ERROR_PATTERN).fill_null(False))
                .unique("Transaction ID", keep="first", maintain_order=True)
                .iter_rows(named=True)
            ):
                _bank_error(
                    f"Transactions_{row['Date'].year}",
                    row["Transaction ID"],
                    "TRANSACTION_SPREADSHEET_ERROR",
                    f"transaction on [{row['Account']}] column [{column}] holds spreadsheet error [{row[column]}]",
                )
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
            balances_current_df.filter(pl.col("Balance Auto").is_not_null())
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

        # 8.1 Sync Drive
        if committed and drive_folder is not None and not plugin.config.disable_drive_uploads:
            for file_path, file_status in self.drive_synchronise(drive_folder, self.local_cache, download=False, upload=True, errors=errors).items():
                if file_status in (plugin.DriveStatus.CONFLICTED, plugin.DriveStatus.FAILED):
                    files_conflicted.add(file_path)
        years_conflicted = {_bank_file(path)[1] for path in files_conflicted if re.fullmatch(FILE_NAME_PATTERN, basename(path)) and _bank_file(path)[0].endswith("_transactions")}

        upload_started_time = time.time()
        tabs_uploaded, tabs_unchanged, tabs_moved, tabs_failed = [], [], [], []

        def _bank_tab_uploaded(_tab, _render_df, _raw_columns, _formula_columns, _dropdown_columns, _highlight_cells, _schema, _before=None, _after=None):
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
                decimal_columns=[column for column, dtype in _schema.items() if dtype == pl.Float64 and column in _render_df.columns],
                sheet_before=_before,
                sheet_after=_after,
                check=not plugin.config.force_reprocessing,
                guard=True,
                schema=_schema,
            )
            {plugin.UploadStatus.UNCHANGED: tabs_unchanged, plugin.UploadStatus.MOVED: tabs_moved, plugin.UploadStatus.FAILED: tabs_failed}.get(_status, tabs_uploaded).append(_tab)
            return _status

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

            # 9.1 Upload Accounts Tab
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

            # 9.2 Upload Balances Tab
            tabs_status: dict[str, plugin.UploadStatus] = {}
            if balances_held or tab_edited.get("Balances", set()) & files_conflicted:
                self.print_log("Sheet [Bank:Balances] skipped, a balances file conflicted on Drive or was left as committed", level="warn")
            elif len(balances_current_df):
                started_time = time.time()
                manual_ids = _bank_manual_readings()["Balance ID"].implode()
                balances_active_df = (
                    balances_current_df.join(accounts_current_df, on="Account ID", how="left")
                    .filter(pl.col("Status").fill_null("") != ACCOUNT_STATUS_CLOSED)
                    .filter((pl.col("Status").fill_null("") != ACCOUNT_STATUS_MANUAL) | pl.col("Balance ID").is_in(manual_ids))
                )
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
                manual_letter = _bank_letter(list(BALANCES_SCHEMA), "Balance Manual")
                manual_cells = [f"{manual_letter}{index + 2}" for index, manual in enumerate(balances_sheet_df["Balance ID"].is_in(manual_ids).to_list()) if manual]
                dataframe_print(self.name, balances_sheet_df, print_label="Balances", print_verb="rendered", started=started_time)
                tabs_status["Balances"] = _bank_tab_uploaded("Balances", balances_sheet_df, BALANCES_RAW_COLUMNS, {"Balance": BALANCES_BALANCE_FORMULA}, {}, manual_cells, BALANCES_SCHEMA)

            # 9.3 Upload Transactions Tabs
            transactions_tab_years = sorted({*_bank_years(), *(int(tab.rsplit("_", 1)[-1]) for tab in sheet_files if re.fullmatch(r"Transactions_\d{4}", tab))})
            sheet_columns = list(TRANSACTIONS_YEAR_TAB_SCHEMA)
            for year in transactions_tab_years:
                tab = f"Transactions_{year}"
                if year in years_conflicted or year in years_held:
                    self.print_log(f"Sheet [Bank:{tab}] skipped, a file of its year conflicted on Drive or was left as committed", level="warn")
                    continue
                started_time = time.time()
                year_sheet_df = _bank_tab_rendered(transactions_current_df.filter(pl.col("Date").dt.year() == year))
                if len(year_sheet_df) == 0 and tab not in sheet_files:
                    continue
                dataframe_print(self.name, year_sheet_df, print_label=tab, print_verb="rendered", started=started_time)
                tabs_status[tab] = _bank_tab_uploaded(
                    tab,
                    year_sheet_df,
                    TRANSACTIONS_RAW_COLUMNS,
                    {"Category": TRANSACTIONS_CATEGORY_FORMULA, "Bucket": TRANSACTIONS_BUCKET_FORMULA},
                    {"Vetted": FLAGS, "Category Manual": TRANSACTIONS_CATEGORY_OPTIONS},
                    [_bank_letter(sheet_columns, column) for column in TRANSACTIONS_EDIT_COLUMNS],
                    TRANSACTIONS_YEAR_TAB_SCHEMA,
                    [f"Transactions_{older}" for older in transactions_tab_years if older < year],
                    ["Transactions", *(f"Transactions_{newer}" for newer in transactions_tab_years if newer > year)],
                )

            # 10.1 Commit Bases
            for tab, status in tabs_status.items():
                uploaded_path = self._sheet_cache_path(f"bank_{tab}".lower())
                if status == plugin.UploadStatus.UPLOADED and uploaded_path is not None:
                    shutil.copyfile(uploaded_path, abspath(f"{self.local_cache}/__bank_tab_{tab.lower()}.csv"))
                elif tab in tab_merged and not tab_edited.get(tab, set()) & files_conflicted:
                    shutil.copyfile(sheet_files[tab], abspath(f"{self.local_cache}/__bank_tab_{tab.lower()}.csv"))

            # 9.4 Upload Summary Tab
            if len(transactions_current_df):
                started_time = time.time()
                transactions_month_df = (
                    transactions_current_df.filter(pl.col("Date") < month_start)
                    .with_columns(TRANSACTIONS_END_OF_MONTH, (-pl.col("Amount Split")).alias("__total"))
                    .filter(
                        ((pl.col("Vetted") == FLAG_YES) & pl.col("Category").is_not_null() & pl.col("Bucket").is_not_null()).fill_null(False).all().over("End of Month")
                        & (pl.col("Bucket") != TRANSACTIONS_BUCKET_EXCLUDED)
                    )
                )

                def _bank_included(_names: pl.Series, _noun: str, _nouns: str) -> str | None:
                    _words = [" ".join(_word if len(_word) > 1 and _word.isupper() else _word.lower() for _word in _name.split()) for _name in _names.to_list()]
                    if not _words:
                        return None
                    if len(_words) == 1:
                        return f"Includes the {_words[0]} {_noun} this month"
                    return f"Includes {', '.join(_words[:-1])} & {_words[-1]} {_nouns} this month"

                transactions_categories_df = (
                    transactions_month_df.group_by(["End of Month", "Bucket", "Category"])
                    .agg(pl.col("__total").sum().round(2).alias("Total"), pl.lit(2).alias("__level"))
                    .filter(pl.col("Total") != 0)
                    .join(
                        classifier_df.filter(pl.col("Pattern").is_null() & pl.col("Description").is_not_null())
                        .unique("Category", keep="first", maintain_order=True)
                        .select(["Category", "Description"]),
                        on="Category",
                        how="left",
                    )
                )
                transactions_buckets_df = (
                    transactions_month_df.group_by(["End of Month", "Bucket"])
                    .agg(pl.col("__total").sum().round(2).alias("Total"), pl.lit(1).alias("__level"))
                    .join(transactions_categories_df.group_by(["End of Month", "Bucket"]).agg(pl.col("Category").sort().alias("__included")), on=["End of Month", "Bucket"], how="left")
                    .with_columns(pl.col("__included").map_elements(lambda _names: _bank_included(_names, "category", "categories"), return_dtype=pl.Utf8).alias("Description"))
                )
                transactions_months_df = (
                    transactions_month_df.group_by("End of Month")
                    .agg(pl.col("__total").sum().round(2).alias("Total"), pl.lit(0).alias("__level"))
                    .join(transactions_buckets_df.group_by("End of Month").agg(pl.col("Bucket").sort().alias("__included")), on="End of Month", how="left")
                    .with_columns(pl.col("__included").map_elements(lambda _names: _bank_included(_names, "bucket", "buckets"), return_dtype=pl.Utf8).alias("Description"))
                )
                transactions_tab_df = (
                    pl.concat([transactions_months_df, transactions_buckets_df, transactions_categories_df], how="diagonal_relaxed")
                    .sort(["__level", "End of Month", "Bucket", "Category"], descending=[False, True, False, False])
                    .select(list(TRANSACTIONS_TAB_SCHEMA))
                )
                if len(transactions_tab_df) or self.sheet_cached("Bank", "Transactions") is not None:
                    dataframe_print(self.name, transactions_tab_df, print_label="Transactions", print_verb="totalled", started=started_time)
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

        # 9.5 Upload Logs Tab
        logs_df = self.logs_merged(errors, today)
        if committed:
            _bank_tab_uploaded("Logs", logs_df, plugin.LOG_RAW_COLUMNS, {}, {}, [], plugin.LOG_SCHEMA)
        self.print_log(f"Tabs uploaded [{', '.join(tabs_uploaded)}] skipped unchanged [{', '.join(tabs_unchanged)}] skipped moved [{', '.join(tabs_moved)}] failed [{', '.join(tabs_failed)}]")
        self.print_log("Upload complete", started=upload_started_time)

        # 10.2 Log Changes
        if committed and changes_frames:
            changes_df = pl.concat(changes_frames, how="diagonal_relaxed").filter(
                ~pl.col("Year File").is_in([basename(path) for path in files_conflicted]) & ~pl.col("Year File").str.extract(r"_(\d{4})\.csv$").cast(pl.Int64).is_in(list(years_held))
            )
            if len(changes_df):
                changes_file = abspath(f"{self.local_cache}/{CHANGES_FILE_PREFIX}_{today:%Y_%m}.csv")
                changes_md5 = {year_file: md5 for year_file in changes_df["Year File"].unique().to_list() if (md5 := _bank_md5(abspath(join(self.local_cache, year_file)).lower())) is not None}
                changes_df = changes_df.with_columns(pl.col("Year File").replace_strict(changes_md5, default=None, return_dtype=pl.Utf8).alias("File MD5")).select(list(CHANGES_SCHEMA))
                if isfile(changes_file):
                    changes_df = pl.concat([self.csv_read(changes_file, schema=CHANGES_SCHEMA, print_rows=0).select(list(CHANGES_SCHEMA)), changes_df], how="vertical_relaxed")
                self.csv_write(changes_df, changes_file, print_verb="appended", print_rows=0, float_precision=AMOUNT_DECIMALS)

        # 10.3 Commit Files
        if committed:
            if not files_conflicted:
                if len(accounts_df):
                    self.csv_write(accounts_df.select(list(ACCOUNTS_SCHEMA)), accounts_snapshot_file, print_rows=0)
                elif isfile(accounts_snapshot_file):
                    os.remove(accounts_snapshot_file)
                if len(classifier_df) and not classifier_held:
                    self.csv_write(classifier_df.select(list(CLASSIFIER_SCHEMA)), classifier_snapshot_file, print_rows=0)
            files_recorded = dict(files_committed)
            for path in [*_bank_paths("redbark_balances", "manual_balances"), *_bank_paths("redbark_transactions", "manual_transactions")]:
                family, year = _bank_file(path)
                held = year in years_held or (_bank_changed(path) and year not in transactions_committed)
                if family.endswith("_balances"):
                    held = year in balances_held or (_bank_changed(path) and year not in balances_committed)
                if path not in files_conflicted and path not in files_unreadable and not held:
                    files_recorded[basename(path)] = cast(str, _bank_md5(path))
            for path in exports:
                if path not in files_conflicted and (path in exports_imported or basename(path) in files_committed):
                    files_recorded[basename(path)] = exports_md5[path]
            if files_recorded != files_committed:
                with open(f"{files_committed_file}.tmp", "w") as files_committed_handle:
                    json.dump(dict(sorted(files_recorded.items())), files_committed_handle, indent=2)
                os.replace(f"{files_committed_file}.tmp", files_committed_file)
        if not len(balances_delta_df) and not len(transactions_delta_df):
            self.print_log("No new data found")

    def __init__(self):
        super().__init__(
            "Bank",
            order=30,
            repos=REPOS_BANK,
            error_codes=ERROR_CODES,
            drive_download_only=("activity*.csv", "amex_*"),
            throttles={"redbark": plugin.REDBARK_BACKOFF, "google_drive": plugin.GOOGLE_DRIVE_BACKOFF, "google_sheets": plugin.GOOGLE_SHEETS_BACKOFF},
        )


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


def bank_canonical(column):
    return pl.col(column).fill_null("").str.replace_all(r"\s+", " ").str.strip_chars()


def bank_balances_identified(balances_df: pl.DataFrame) -> pl.DataFrame:
    balances_df = balances_df.with_columns(pl.col("Time").str.zfill(8))
    return balances_df.with_columns(
        pl.Series("Balance ID", [bank_record_id(BALANCE_ID_NAMESPACE, *identity) for identity in balances_df.select(["Account ID", "Date", "Time"]).iter_rows()], dtype=pl.Utf8)
    )


def bank_transactions_identified(transactions_df: pl.DataFrame) -> pl.DataFrame:
    identity = ["Account ID", "Date", "__cents", "__description"]
    indexed_df = (
        transactions_df.drop(["Split", "Transaction ID"], strict=False)
        .with_row_index("__row")
        .with_columns(
            bank_cents("Amount").alias("__cents"),
            (pl.col("Amount Split").fill_null(pl.col("Amount")) * 100).round().cast(pl.Int64).alias("__split_cents"),
            bank_canonical("Description").alias("__description"),
        )
    )
    identified_df = (
        indexed_df.drop_nulls(["Account ID", "Date", "__cents"])
        .with_columns((pl.col("__split_cents").cum_sum().over(identity) - pl.col("__split_cents")).alias("__before"))
        .with_columns(pl.when(pl.col("__cents") == 0).then(pl.int_range(pl.len()).over(identity)).otherwise(pl.col("__before") // pl.col("__cents")).alias("__ordinal"))
        .with_columns(pl.when(pl.len().over([*identity, "__ordinal"]) == 1).then(0).otherwise(pl.int_range(1, pl.len() + 1).over([*identity, "__ordinal"])).cast(pl.Int64).alias("Split"))
    )
    identified_df = identified_df.with_columns(
        pl.Series("Transaction ID", [bank_record_id(TRANSACTION_ID_NAMESPACE, *key) for key in identified_df.select([*identity, pl.col("__ordinal")]).iter_rows()], dtype=pl.Utf8)
    )
    return indexed_df.join(identified_df.select(["__row", "Split", "Transaction ID"]), on="__row", how="left").sort("__row").drop(["__row", "__cents", "__split_cents", "__description"])


def bank_tab_edits(tab_df: pl.DataFrame, base_df: pl.DataFrame) -> tuple[dict[str, dict], int, int]:
    present = [column for column in TRANSACTIONS_EDIT_COLUMNS if column in tab_df.columns]

    def flagged(_typed_df):
        _typed_df = _typed_df.with_columns(
            [pl.lit(None, dtype=pl.Int64 if _column == "Amount Split" else pl.Utf8).alias(_column) for _column in TRANSACTIONS_EDIT_COLUMNS if _column not in _typed_df.columns]
        )
        return _typed_df.with_columns(bank_flag("Vetted").alias("__flag"), pl.col("Vetted").alias("__vetted"))

    def parts(_typed_df, _columns):
        _parts: dict[str, list[dict]] = {}
        for _row in _typed_df.filter(pl.col("Transaction ID").is_not_null()).select(["Transaction ID", *_columns]).iter_rows(named=True):
            _parts.setdefault(_row["Transaction ID"], []).append({_column: _row[_column] for _column in _columns})
        return _parts

    def ordered(_parts, _columns):
        return sorted(tuple((_part[_column] is None, "" if _part[_column] is None else str(_part[_column])) for _column in _columns) for _part in _parts)

    tab_df, base_df = flagged(tab_df), flagged(base_df)
    fixed = [column for column in TRANSACTIONS_FIXED_COLUMNS if column in tab_df.columns and column in base_df.columns]
    tab_parts = parts(tab_df.with_columns(pl.coalesce(pl.col("__flag"), pl.concat_str(pl.lit("!"), pl.col("__vetted"))).alias("Vetted")), [*TRANSACTIONS_EDIT_COLUMNS, "__vetted"])
    base_parts = parts(base_df.with_columns(pl.col("__flag").alias("Vetted")), TRANSACTIONS_EDIT_COLUMNS)
    tab_fixed, base_fixed = parts(tab_df, fixed), parts(base_df, fixed)
    tab_rows = {
        row["Transaction ID"]: row
        for row in tab_df.filter(pl.col("Transaction ID").is_not_null()).unique("Transaction ID", keep="first", maintain_order=True).select(["Transaction ID", *fixed]).iter_rows(named=True)
    }
    edits, ignored = {}, 0
    for transaction_id, tab_id_parts in tab_parts.items():
        base_id_parts = base_parts.get(transaction_id, [])
        if transaction_id in base_fixed and set(ordered(tab_fixed[transaction_id], fixed)) != set(ordered(base_fixed[transaction_id], fixed)):
            ignored += 1
        if ordered(tab_id_parts, present) == ordered(base_id_parts, present):
            continue
        row = tab_rows[transaction_id]
        edits[transaction_id] = {
            "Tab": [{column: part[column] for column in TRANSACTIONS_EDIT_COLUMNS} for part in tab_id_parts],
            "Base": base_id_parts,
            "Present": present,
            "Bad Vetted": next((part["__vetted"] for part in tab_id_parts if part["Vetted"] is not None and part["Vetted"].startswith("!")), None),
            "Source ID": row.get("Source ID"),
            "Account ID": row.get("Account ID"),
            "Amount": row.get("Amount"),
            "Date": row.get("Date"),
        }
    idless = len(tab_df.filter(pl.col("Transaction ID").is_null() & ~pl.all_horizontal([pl.col(column).is_null() for column in tab_df.columns if not column.startswith("__")])))
    return edits, ignored, idless


def bank_export_parsed(content: bytes) -> tuple[pl.DataFrame, int]:
    rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n"))))
    if not rows or [cell.strip() for cell in rows[0]] != EXPORT_COLUMNS:
        raise ValueError(f"header [{', '.join(rows[0]) if rows else ''}] not [{', '.join(EXPORT_COLUMNS)}]")
    parsed, pending = [], 0
    for number, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue
        if len(row) != len(EXPORT_COLUMNS):
            raise ValueError(f"row [{number}] has [{len(row)}] cells")
        record = dict(zip(EXPORT_COLUMNS, (cell.strip() for cell in row), strict=True))
        try:
            made = datetime.strptime(record["Date"], "%d/%m/%Y").replace(tzinfo=UTC).date()
            posted = datetime.strptime(record["Date Processed"], "%d/%m/%Y").replace(tzinfo=UTC).date() if record["Date Processed"] else None
            amount = Decimal(record["Amount"].replace("$", "").replace(",", ""))
        except (ValueError, InvalidOperation) as exception:
            raise ValueError(f"row [{number}] unparsed") from exception
        if not amount.is_finite() or cast(int, amount.as_tuple().exponent) < -2:
            raise ValueError(f"row [{number}] amount has more than two decimals")
        if posted is None:
            pending += 1
            continue
        parsed.append({"Date": made, "Date Posted": posted, "Amount": -float(amount), "Description": record["Description"], "Card": record["Account #"] or None})
    return pl.DataFrame(parsed, schema=EXPORT_SCHEMA), pending


def bank_export_account(export_df: pl.DataFrame, cards: dict[str, str], accounts_df: pl.DataFrame, held_df: pl.DataFrame) -> tuple[str | None, str]:
    known = {cards[card] for card in export_df["Card"].drop_nulls().unique().to_list() if card in cards}
    if len(known) == 1:
        return known.pop(), "card"
    if len(known) > 1:
        return None, "cards of more than one account"
    canonical = bank_canonical("Description").alias("__description")
    keys_df = export_df.select(["Date", bank_cents("Amount").alias("__cents"), canonical])
    overlapping = []
    for account_id in accounts_df["Account ID"].to_list():
        account_df = held_df.filter(pl.col("Account ID") == account_id).select(["Date", bank_cents("Amount").alias("__cents"), canonical]).unique()
        if len(account_df) == 0:
            continue
        span_df = keys_df.filter(pl.col("Date") <= account_df["Date"].max())
        if len(span_df) and len(span_df.join(account_df, on=["Date", "__cents", "__description"], how="semi")) >= EXPORT_OVERLAP_SHARE * len(span_df):
            overlapping.append(account_id)
    if len(overlapping) == 1:
        return overlapping[0], "overlap"
    return None, "overlap with more than one account" if overlapping else "no overlap"
