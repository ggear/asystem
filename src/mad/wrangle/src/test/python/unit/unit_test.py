import sys
from os.path import dirname

sys.path.insert(0, dirname(__file__))

import collections
import copy
import csv
import dataclasses
import datetime
import filecmp
import functools
import glob
import hashlib
import importlib
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
import unittest
import urllib.error
import urllib.parse
import urllib.response
from collections.abc import Iterable
from datetime import date as date_type
from email.message import Message
from os.path import abspath, basename, dirname, getmtime, isdir, isfile, join, realpath
from pathlib import Path
from unittest import mock

import csv_diff
import google.oauth2.service_account
import googleapiclient.errors
import gspread.exceptions
import httplib2
import pandas as pd
import polars as pl
import pytest
import requests
import yfinance.exceptions
from googleapiclient.discovery import build

sys.path.append("../../../main/python")

from wrangle import main as wrangle_main
from wrangle import plugin
from wrangle.plugin import DownloadResult, DownloadStatus, Plugin, database
from wrangle.plugin._throttle import Throttle, google_failed, urllib_failed, yahoo_failed
from wrangle.plugin.bank import BALANCES_KEY_COLUMNS as BANK_BALANCES_KEY_COLUMNS
from wrangle.plugin.bank import (
    BALANCES_MAX_AGE_HOURS,
    BALANCES_SCHEMA,
    REPOS_BANK,
    TRANSACTIONS_SCHEMA,
    TRANSACTIONS_YEAR_TAB_SCHEMA,
    bank_export_account,
    bank_export_parsed,
    bank_flag,
    bank_tab_edits,
)
from wrangle.plugin.bank import BALANCES_STATE_SCHEMA as BANK_BALANCES_STATE_SCHEMA
from wrangle.plugin.bank import (
    TRANSACTIONS_KEY_COLUMNS as BANK_TRANSACTIONS_KEY_COLUMNS,
)
from wrangle.plugin.bank import (
    TRANSACTIONS_STATE_SCHEMA as BANK_TRANSACTIONS_STATE_SCHEMA,
)
from wrangle.plugin.config import LOG_SCHEMA, get_file
from wrangle.plugin.counters import *
from wrangle.plugin.counters import CTR_TZ
from wrangle.plugin.currency import COLUMNS as CURRENCY_COLUMNS
from wrangle.plugin.currency import REPOS_CURRENCY
from wrangle.plugin.equity import (
    DIMENSIONS_STATE,
    PORTFOLIO_TICKERS_ACTIVE,
    PORTFOLIO_TICKERS_MANUAL,
    PORTFOLIO_TICKERS_NODATA,
    REPOS_EQUITY,
    STOCK,
)
from wrangle.plugin.interest import COLUMNS as INTEREST_COLUMNS
from wrangle.plugin.interest import REPOS_INTEREST
from wrangle.plugin.logger import dataframe_print, print_log
from wrangle.server import feeds
from wrangle.server.server import CHART_SPEC, STATIC_ROOT_DIR, TEMPLATE, THEMES

########################################################################################################################
# NOTES:
#   - Include in test runner templates for realtime, unbuffered output: PYTHONUNBUFFERED=1;JB_DISABLE_BUFFERING=1
########################################################################################################################


pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning:multiprocessing")

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))


class WrangleTest(unittest.TestCase):
    ########################################################################################################################
    # Bank
    ########################################################################################################################

    # No data, nothing committed and no error
    def test_bank_local_blank_1(self):
        self._bank_run(
            "blank_1",
            rerun=False,
            file_asserts={
                "__bank_balances_current.csv": [assert_file_does_not_exist()],
            },
        )

    # An unreadable balances file on a reprocess errors the file and commits nothing
    def test_bank_local_corrupt_1(self):
        self._bank_run(
            "corrupt_1",
            rerun=False,
            force=True,
            errored={plugin.CTR_SRC_DATA: 1, plugin.CTR_SRC_FILES: 1},
            file_asserts={
                "__bank_balances_current.csv": [assert_file_does_not_exist()],
            },
        )

    # An account renamed from its from date, with no committed snapshot, re-derives every balance
    def test_bank_local_replete_1(self):
        self._bank_run(
            "replete_1",
            today="2026-03-01T12:00:00",
            counters={plugin.CTR_SRC_FILES: {plugin.CTR_ACT_PROCESSED: 1}},
            file_asserts={
                "__bank_balances_current.csv": [
                    assert_file_size(min_rows=6, max_rows=6),
                    assert_file_column_values("Account", ["Old One", "Two", "Three", "One", "Two", "Three"], sort_by=["Date", "Account Number"]),
                    assert_file_column_values("Account Type", ["Asset"] * 6),
                    assert_file_column_distinct("Account ID", 3),
                ],
                "__bank_accounts_dimension.csv": [assert_file_size(min_rows=4, max_rows=4)],
            },
        )

    # Two numbers share a name in sequence without error, an account on no accounts row is unmapped
    def test_bank_local_partial_1(self):
        self._bank_run(
            "partial_1",
            today="2026-03-01T12:00:00",
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "__bank_balances_current.csv": [
                    assert_file_size(min_rows=4, max_rows=4),
                    assert_file_column_values("Account", ["Shared", "Raw Three", "Shared", "Raw Three"], sort_by=["Date", "Balance"]),
                    assert_file_column_distinct("Account ID", 3),
                ],
                "__bank_logs.csv": [assert_file_column_values("Code", ["ACCOUNT_UNMAPPED"])],
            },
        )

    # A padded key maps, a future from date, a blank name and an unknown number are source errors
    def test_bank_local_partial_2(self):
        self._bank_run(
            "partial_2",
            today="2026-03-01T12:00:00",
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 3},
            file_asserts={
                "__bank_balances_current.csv": [
                    assert_file_size(min_rows=4, max_rows=4),
                    assert_file_column_values("Account", ["One", "Raw Two", "Raw Three", "Raw Other"], sort_by=["Balance"]),
                ],
                "__bank_logs.csv": [assert_file_column_values("Code", ["ACCOUNT_FROM", "ACCOUNT_NAME", "ACCOUNT_UNMAPPED"], sort_by=["Code"])],
            },
        )

    # The same reading in a Redbark and a manual file commits once
    def test_bank_local_partial_3(self):
        self._bank_run(
            "partial_3",
            counters={plugin.CTR_SRC_FILES: {plugin.CTR_ACT_PROCESSED: 2}},
            file_asserts={
                "__bank_balances_current.csv": [
                    assert_file_size(min_rows=2, max_rows=2),
                    assert_file_column_distinct("Balance ID", 2),
                ],
            },
        )

    # No accounts tab, every reading keeps its stored name without error
    def test_bank_local_partial_66(self):
        self._bank_run(
            "partial_66",
            rerun=False,
            force=True,
            file_asserts={
                "__bank_balances_current.csv": [
                    assert_file_size(min_rows=3, max_rows=3),
                    assert_file_column_values("Account", ["Raw One", "Raw Two", "Raw Three"], sort_by=["Balance"]),
                ],
            },
        )

    # A row lacking its account id errors its file only, the other file commits
    def test_bank_local_corrupt_2(self):
        self._bank_run(
            "corrupt_2",
            rerun=False,
            force=True,
            errored={plugin.CTR_SRC_FILES: 1},
            file_asserts={
                "__bank_balances_current.csv": [
                    assert_file_size(min_rows=3, max_rows=3),
                    assert_file_dates(start_date="2026-01-15", end_date="2026-01-15"),
                ],
            },
        )

    # Two rows for one account on one date make the accounts tab unusable, balances commit under stored names
    def test_bank_local_corrupt_3(self):
        self._bank_unusable("corrupt_3")

    # A header only accounts tab is unusable, balances commit under stored names
    def test_bank_local_corrupt_6(self):
        self._bank_unusable("corrupt_6")

    # Accounts rows all lacking a natural key make the tab unusable, balances commit under stored names
    def test_bank_local_corrupt_7(self):
        self._bank_unusable("corrupt_7")

    # An accounts tab missing a natural key column is unusable, balances commit under stored names
    def test_bank_local_corrupt_8(self):
        self._bank_unusable("corrupt_8")

    # An unparseable from date makes the accounts tab unusable, balances commit under stored names
    def test_bank_local_corrupt_9(self):
        self._bank_unusable("corrupt_9")

    # An empty accounts tab is unusable and drops the committed snapshot
    def test_bank_local_corrupt_5(self):
        self._bank_unusable("corrupt_5", {"__bank_accounts_dimension.csv": [assert_file_does_not_exist()]})

    # Two accounts holding one name on one date are a source error, both readings commit
    def test_bank_local_corrupt_4(self):
        self._bank_run(
            "corrupt_4",
            rerun=False,
            force=True,
            errored={plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "__bank_balances_current.csv": [
                    assert_file_column_values("Account", ["Shared", "Shared"]),
                    assert_file_column_distinct("Account ID", 2),
                ],
                "__bank_logs.csv": [assert_file_column_values("Code", ["ACCOUNT_NAME_SHARED"])],
            },
        )

    # A first live run appends the unlisted Redbark account, writes the opening balances and sweeps no transactions
    def test_bank_local_partial_4(self):
        self._bank_run(
            "partial_4",
            source=True,
            counters={plugin.CTR_SRC_SOURCES: {plugin.CTR_ACT_DOWNLOADED: 3}, plugin.CTR_SRC_FILES: {plugin.CTR_ACT_PROCESSED: 1}},
            file_asserts={
                "_sheet_bank_accounts.csv": [
                    assert_file_column_values("Name", ["One", "Raw Two"]),
                    assert_file_column_values("Status", ["Linked", "Linked"]),
                    assert_file_column_values("Redbark Account ID", ["a1", "a2"]),
                ],
                "redbark_balances_2026.csv": [
                    assert_file_size(min_rows=2, max_rows=2),
                    assert_file_column_values("Time", ["11:30:00", "11:30:00"]),
                ],
                "redbark_transactions_2026.csv": [assert_file_does_not_exist()],
                "__bank_balances_current.csv": [
                    assert_file_column_values("Account", ["One", "Raw Two"], sort_by=["Account Number"]),
                    assert_file_column_values("Account ID", ["540a8918175f5ca38559395087eb552c", "69c576ba31725c77a2ff31acd55cfbca"], sort_by=["Account Number"]),
                    assert_file_column_values("Balance ID", ["37ed8e10f7d050c6951841974740007e", "a1e3d87b9b5f568bbcd41557cf6c1300"], sort_by=["Account Number"]),
                ],
            },
        )

    # A balances file stamped an hour ago is fresh, nothing is requested
    def test_bank_local_partial_5(self):
        self._bank_run(
            "partial_5",
            source=True,
            rerun=False,
            counters={plugin.CTR_SRC_SOURCES: {plugin.CTR_ACT_DOWNLOADED: 0}, plugin.CTR_SRC_FILES: {plugin.CTR_ACT_PROCESSED: 1}},
            file_asserts={
                "redbark_balances_2026.csv": [assert_file_size(min_rows=2, max_rows=2)],
                "__bank_balances_current.csv": [assert_file_size(min_rows=2, max_rows=2)],
            },
        )

    # A balances file stamped three hours ago is due, unchanged balances only stamp it and transactions are still fetched
    def test_bank_local_partial_6(self):
        self._bank_run(
            "partial_6",
            source=True,
            counters={plugin.CTR_SRC_SOURCES: {plugin.CTR_ACT_DOWNLOADED: 2}, plugin.CTR_SRC_FILES: {plugin.CTR_ACT_PROCESSED: 2}},
            file_asserts={
                "redbark_balances_2026.csv": [assert_file_size(min_rows=2, max_rows=2)],
                "redbark_transactions_2026.csv": [assert_file_column_values("Source ID", ["t1"])],
            },
        )

    # A moved balance appends a reading and sweeps seven years of transactions into their year files
    def test_bank_local_partial_7(self):
        self._bank_run(
            "partial_7",
            standing=2,
            source=True,
            counters={plugin.CTR_SRC_SOURCES: {plugin.CTR_ACT_DOWNLOADED: 2}, plugin.CTR_SRC_FILES: {plugin.CTR_ACT_PROCESSED: 3}},
            file_asserts={
                "redbark_balances_2026.csv": [
                    assert_file_size(min_rows=3, max_rows=3),
                    assert_file_column_values("Time", ["11:30:00", "09:00:00", "09:00:00"]),
                ],
                "redbark_transactions_2026.csv": [
                    assert_file_size(min_rows=1, max_rows=1),
                    assert_file_column_values("Source ID", ["t1"]),
                    assert_file_column_values("Merchant Code", ["5812"]),
                    assert_file_column_values("Bank Code", ["FOOD_AND_DRINK"]),
                ],
                "redbark_transactions_2020.csv": [assert_file_column_values("Source ID", ["t0"])],
                "redbark_transactions_2018.csv": [assert_file_does_not_exist()],
                "__bank_balances_current.csv": [assert_file_size(min_rows=3, max_rows=3)],
                "__bank_transactions_current.csv": [assert_file_size(min_rows=2, max_rows=2)],
            },
        )

    # The first check of a year writes its opening balances to a new year file
    def test_bank_local_partial_8(self):
        self._bank_run(
            "partial_8",
            source=True,
            counters={plugin.CTR_SRC_FILES: {plugin.CTR_ACT_PROCESSED: 2}},
            file_asserts={
                "redbark_balances_2025.csv": [assert_file_size(min_rows=2, max_rows=2)],
                "redbark_balances_2026.csv": [assert_file_size(min_rows=2, max_rows=2)],
                "__bank_balances_current.csv": [assert_file_size(min_rows=3, max_rows=3)],
            },
        )

    # The first check of a year compares against the previous year file, nothing moved
    def test_bank_local_partial_46(self):
        self._bank_run(
            "partial_46",
            source=True,
            counters={plugin.CTR_SRC_SOURCES: {plugin.CTR_ACT_DOWNLOADED: 2}, plugin.CTR_SRC_FILES: {plugin.CTR_ACT_PROCESSED: 2}},
            file_asserts={
                "redbark_balances_2026.csv": [assert_file_size(min_rows=2, max_rows=2)],
                "redbark_transactions_2026.csv": [assert_file_does_not_exist()],
                "__bank_balances_current.csv": [assert_file_size(min_rows=4, max_rows=4)],
            },
        )

    # The first check of a month appends its opening balances though nothing moved
    def test_bank_local_partial_36(self):
        self._bank_run(
            "partial_36",
            today="2026-02-02T12:00:00",
            source=True,
            counters={plugin.CTR_SRC_SOURCES: {plugin.CTR_ACT_DOWNLOADED: 2}, plugin.CTR_SRC_FILES: {plugin.CTR_ACT_PROCESSED: 1}},
            file_asserts={
                "redbark_balances_2026.csv": [
                    assert_file_size(min_rows=4, max_rows=4),
                    assert_file_dates(start_date="2026-01-15", end_date="2026-02-02"),
                ],
                "redbark_transactions_2026.csv": [assert_file_does_not_exist()],
                "__bank_balances_current.csv": [assert_file_size(min_rows=4, max_rows=4)],
            },
        )

    # An unreadable current balances file is kept and errors the file, transactions still fetched
    def test_bank_local_corrupt_11(self):
        self._bank_run(
            "corrupt_11",
            source=True,
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 1, plugin.CTR_SRC_FILES: 1},
            counters={plugin.CTR_SRC_SOURCES: {plugin.CTR_ACT_DOWNLOADED: 1}},
            file_asserts={
                "redbark_balances_2026.csv": [assert_file_does_exist()],
                "__bank_balances_current.csv": [assert_file_does_not_exist()],
                "__bank_logs.csv": [assert_file_column_values("Code", ["FILE_UNREADABLE"])],
            },
        )

    # Duplicated, valueless and unknown live balances are one source error, the valid one is stored
    def test_bank_local_corrupt_12(self):
        self._bank_run(
            "corrupt_12",
            source=True,
            rerun=False,
            file_asserts={
                "redbark_balances_2026.csv": [assert_file_size(min_rows=1, max_rows=1), assert_file_column_values("Account", ["One"])],
            },
        )

    # A balances response with no balances is a source error, the absent account a data error
    def test_bank_local_corrupt_13(self):
        self._bank_run(
            "corrupt_13",
            source=True,
            rerun=False,
            file_asserts={
                "__bank_logs.csv": [assert_file_column_values("Code", ["BALANCE_ABSENT", "BALANCE_RESPONSE"], sort_by=["Code"])],
                "redbark_balances_2026.csv": [assert_file_does_not_exist()],
                "__bank_balances_current.csv": [assert_file_does_not_exist()],
            },
        )

    # A failed balances call is a source error, writing no file and requesting no transactions
    def test_bank_local_corrupt_14(self):
        self._bank_run(
            "corrupt_14",
            source=True,
            rerun=False,
            file_asserts={
                "__bank_logs.csv": [assert_file_column_values("Code", ["BALANCE_RESPONSE"], sort_by=["Code"])],
                "redbark_balances_2026.csv": [assert_file_does_not_exist()],
                "redbark_transactions_2026.csv": [assert_file_does_not_exist()],
            },
        )

    # An unreadable transactions year file is kept and errors the file, balances commit
    def test_bank_local_corrupt_16(self):
        self._bank_run(
            "corrupt_16",
            source=True,
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 1, plugin.CTR_SRC_FILES: 1},
            file_asserts={
                "redbark_transactions_2026.csv": [assert_file_does_exist()],
                "__bank_transactions_current.csv": [assert_file_does_not_exist()],
                "__bank_balances_current.csv": [assert_file_size(min_rows=3, max_rows=3)],
            },
        )

    # A transactions response missing its status column is a source error, balances commit
    def test_bank_local_corrupt_17(self):
        self._bank_run(
            "corrupt_17",
            source=True,
            rerun=False,
            file_asserts={
                "redbark_transactions_2026.csv": [assert_file_does_not_exist()],
                "__bank_balances_current.csv": [assert_file_size(min_rows=2, max_rows=2)],
            },
        )

    # A failed accounts call is a source error, leaving no linked account to check
    def test_bank_local_corrupt_18(self):
        self._bank_run(
            "corrupt_18",
            source=True,
            rerun=False,
            file_asserts={
                "__bank_logs.csv": [assert_file_column_values("Code", ["REDBARK_ACCOUNTS"], sort_by=["Code"])],
                "redbark_balances_2026.csv": [assert_file_does_not_exist()],
            },
        )

    # A sweep from each account's newest held date less the leeway adds only new transactions
    def test_bank_local_partial_11(self):
        self._bank_run(
            "partial_11",
            source=True,
            file_asserts={
                "redbark_transactions_2026.csv": [
                    assert_file_size(min_rows=3, max_rows=3),
                    assert_file_column_values("Source ID", ["t1", "t2", "t6"], sort_by=["Date"]),
                ],
                "__bank_transactions_current.csv": [assert_file_column_values("Account", ["One", "One", "Two"], sort_by=["Date"])],
            },
        )

    # A posting inside the leeway lands in the previous year's file, one before the window is not fetched
    def test_bank_local_partial_12(self):
        self._bank_run(
            "partial_12",
            standing=2,
            source=True,
            file_asserts={
                "redbark_transactions_2025.csv": [assert_file_size(min_rows=1, max_rows=1), assert_file_column_values("Source ID", ["t7"])],
                "redbark_transactions_2026.csv": [assert_file_size(min_rows=2, max_rows=2), assert_file_column_values("Source ID", ["t3", "t9"], sort_by=["Date"])],
                "__bank_transactions_current.csv": [assert_file_size(min_rows=3, max_rows=3)],
            },
        )

    # The accounts call links, duplicates, misses and appends accounts and fills every account id
    def test_bank_local_partial_13(self):
        self._bank_run(
            "partial_13",
            source=True,
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 2},
            file_asserts={
                "_sheet_bank_accounts.csv": [
                    assert_file_columns(["From", "Institution", "Number", "Name", "Type", "Status", "Account ID", "Redbark Account ID", "Redbark Connection ID"]),
                    assert_file_column_values(
                        "Account ID",
                        [
                            "540a8918175f5ca38559395087eb552c",
                            "69c576ba31725c77a2ff31acd55cfbca",
                            "2cc28c0d50e15640a4120ad2a73f56c7",
                            "36bbf924e6895afabff3763234a79275",
                            None,
                            "ecc241accba95d2c8ee7cf5da8c0c66b",
                        ],
                    ),
                    assert_file_column_values("Status", ["Linked", "Duplicate", "Missing", "Missing", None, "Linked"]),
                    assert_file_column_values("Redbark Account ID", ["a1", None, None, None, None, "a4"]),
                ],
                "redbark_balances_2026.csv": [assert_file_size(min_rows=2, max_rows=2)],
                "__bank_logs.csv": [assert_file_column_values("Code", ["ACCOUNT_DUPLICATE", "ACCOUNT_MISSING", "ACCOUNT_MISSING"], sort_by=["Code"])],
            },
        )

    # An id-less held transaction adopts the nearest live one of its amount within three days
    def test_bank_local_partial_14(self):
        self._bank_run(
            "partial_14",
            source=True,
            file_asserts={
                "redbark_transactions_2026.csv": [
                    assert_file_size(min_rows=7, max_rows=7),
                    assert_file_column_values("Source ID", ["l6", "l3", "l1", "l2", None, "l4", "l5"], sort_by=["Date", "Source ID"]),
                ],
                "__bank_transactions_current.csv": [assert_file_column_distinct("Transaction ID", 7)],
            },
        )

    # A first run backfills each account from its from date, else seven years
    def test_bank_local_partial_17(self):
        self._bank_run(
            "partial_17",
            standing=2,
            source=True,
            file_asserts={
                "redbark_balances_2026.csv": [assert_file_size(min_rows=2, max_rows=2)],
                "redbark_transactions_2025.csv": [assert_file_column_values("Source ID", ["t1", "t2"], sort_by=["Date"])],
                "redbark_transactions_2026.csv": [assert_file_column_values("Source ID", ["t3"])],
            },
        )

    # A current balances file holding only its header stores every balance
    def test_bank_local_partial_18(self):
        self._bank_run(
            "partial_18",
            source=True,
            file_asserts={
                "redbark_balances_2026.csv": [assert_file_size(min_rows=2, max_rows=2)],
                "__bank_balances_current.csv": [assert_file_size(min_rows=2, max_rows=2)],
            },
        )

    # Accounts, balances and transactions together, every transaction id pinned
    def test_bank_local_replete_4(self):
        self._bank_run(
            "replete_4",
            source=True,
            file_asserts={
                "redbark_transactions_2025.csv": [assert_file_size(min_rows=3, max_rows=3)],
                "redbark_transactions_2026.csv": [
                    assert_file_size(min_rows=2, max_rows=2),
                    assert_file_column_values("Bank Code", ["FOOD_AND_DRINK", "INCOME"], sort_by=["Date"]),
                    assert_file_column_values("Merchant Code", [None, None], sort_by=["Date"]),
                ],
                "__bank_transactions_current.csv": [
                    assert_file_size(min_rows=5, max_rows=5),
                    assert_file_column_values("Account", ["One", "Two", "One", "One", "Two"], sort_by=["Date"]),
                    assert_file_column_values(
                        "Transaction ID",
                        [
                            "d4352f89b42357ffb06e69a9695667c9",
                            "79c5ee12276f525c84b5abfb49908ed8",
                            "d2ffeef11422516c894c30eb44339739",
                            "61bee1da79965981a8a42ea991258df9",
                            "cfa299a9ce9d5f4daf8e88ac3d081aab",
                        ],
                        sort_by=["Date"],
                    ),
                    assert_file_column_values("Date Posted", [None, None, "2025-11-05", "2026-01-10", "2026-01-12"], sort_by=["Date"]),
                    assert_file_column_values("Split", ["0", "0", "0", "0", "0"]),
                ],
            },
        )

    # A dead Redbark id is replaced from the accounts call and the retried query lands
    def test_bank_local_partial_19(self):
        self._bank_run(
            "partial_19",
            source=True,
            file_asserts={
                "_sheet_bank_accounts.csv": [assert_file_column_values("Redbark Account ID", ["a1n"]), assert_file_column_values("Redbark Connection ID", ["c2"])],
                "redbark_transactions_2026.csv": [assert_file_column_values("Source ID", ["t1"])],
            },
        )

    # A rate limited transactions call is a source error for its account only
    def test_bank_local_corrupt_19(self):
        self._bank_run(
            "corrupt_19",
            source=True,
            rerun=False,
            file_asserts={
                "__bank_logs.csv": [assert_file_column_values("Code", ["TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED_CURRENT", "TRANSACTION_CALL"], sort_by=["Code"])],
                "redbark_transactions_2026.csv": [assert_file_column_values("Source ID", ["t1"])],
            },
        )

    # The first due check of a day sweeps the transactions though no balance moved
    def test_bank_local_partial_20(self):
        self._bank_run(
            "partial_20",
            source=True,
            file_asserts={
                "redbark_balances_2026.csv": [assert_file_size(min_rows=2, max_rows=2)],
                "redbark_transactions_2026.csv": [assert_file_column_values("Source ID", ["t1"])],
            },
        )

    # A changed accounts tab re-derives every balance and transaction in place
    def test_bank_local_replete_2(self):
        self._bank_run(
            "replete_2",
            counters={plugin.CTR_SRC_FILES: {plugin.CTR_ACT_PROCESSED: 2}, plugin.CTR_SRC_DATA: {plugin.CTR_ACT_DELTA_ROWS: 2}},
            file_asserts={
                "__bank_balances_current.csv": [assert_file_size(min_rows=1, max_rows=1), assert_file_column_values("Account", ["Uno"])],
                "__bank_transactions_current.csv": [assert_file_size(min_rows=1, max_rows=1), assert_file_column_values("Account", ["Uno"])],
            },
        )

    # A usable accounts tab with no committed snapshot re-derives every balance
    def test_bank_local_replete_3(self):
        self._bank_run(
            "replete_3",
            counters={plugin.CTR_SRC_FILES: {plugin.CTR_ACT_PROCESSED: 1}},
            file_asserts={
                "__bank_balances_current.csv": [assert_file_column_values("Account", ["One"]), assert_file_column_values("Account Institution", ["Bank A"])],
                "__bank_accounts_dimension.csv": [assert_file_does_exist()],
            },
        )

    # The balances tab holds the current and previous months and each account's latest older reading
    def test_bank_local_partial_9(self):
        self._bank_run(
            "partial_9",
            file_asserts={
                "__bank_balances_current.csv": [assert_file_size(min_rows=8, max_rows=8)],
                "_sheet_bank_balances.csv": [
                    assert_file_columns(list(BALANCES_SCHEMA)),
                    assert_file_column_values("Account", ["Alpha", "Alpha", "Alpha", "Bravo", "Bravo", "Charlie"]),
                    assert_file_column_values("Date", ["2025-12-28", "2025-12-20", "2025-11-25", "2026-01-10", "2026-01-02", "2025-11-20"]),
                    assert_file_column_values("Time", ["09:00:00", "09:00:00", "09:00:00", "15:00:00", "09:00:00", "09:00:00"]),
                ],
            },
        )

    # Unclassified or unvetted rows are an error in a closed month, a warning in the open month
    def test_bank_local_partial_37(self):
        self._bank_run(
            "partial_37",
            standing=3,
            file_asserts={
                "__bank_logs.csv": [
                    assert_file_column_values("Tab", ["Transactions_2023", "Transactions_2025", "Transactions_2025", "Transactions_2026", "Transactions_2026"], sort_by=["Tab", "Code"]),
                    assert_file_column_values(
                        "Code",
                        ["TRANSACTIONS_UNVETTED", "TRANSACTIONS_UNCLASSIFIED", "TRANSACTIONS_UNVETTED", "TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED_CURRENT"],
                        sort_by=["Tab", "Code"],
                    ),
                ],
                "__bank_transactions_current.csv": [
                    assert_file_column_values("Category", ["Health", "Health", "Food", "Food", None, None, None, "Food", None], sort_by=["Date"]),
                    assert_file_column_values("Vetted", ["No", "Yes", "Yes", "Yes", None, None, None, "Yes", None], sort_by=["Date"]),
                ],
            },
        )

    # A year with rows both before and in the open month raises the error and the warning
    def test_bank_local_partial_56(self):
        self._bank_run(
            "partial_56",
            today="2026-02-15T12:00:00",
            standing=5,
            file_asserts={
                "__bank_logs.csv": [
                    assert_file_column_values("Tab", ["Transactions_2023"] + ["Transactions_2025"] * 2 + ["Transactions_2026"] * 4, sort_by=["Tab", "Code"]),
                    assert_file_column_values(
                        "Code",
                        [
                            "TRANSACTIONS_UNVETTED",
                            "TRANSACTIONS_UNCLASSIFIED",
                            "TRANSACTIONS_UNVETTED",
                            "TRANSACTIONS_UNCLASSIFIED",
                            "TRANSACTIONS_UNCLASSIFIED_CURRENT",
                            "TRANSACTIONS_UNVETTED",
                            "TRANSACTIONS_UNVETTED_CURRENT",
                        ],
                        sort_by=["Tab", "Code"],
                    ),
                ],
                "__bank_transactions_current.csv": [
                    assert_file_column_values("Category", ["Health", "Health", "Food", "Food", None, None, None, "Food", None], sort_by=["Date"]),
                    assert_file_column_values("Vetted", ["No", "Yes", "Yes", "Yes", None, None, None, "Yes", None], sort_by=["Date"]),
                ],
            },
        )

    # Vetted typed on the tab is saved title cased, a manual category edit keeps the tick
    def test_bank_local_partial_40(self):
        self._bank_run(
            "partial_40",
            standing=1,
            sheet_downloads=1,
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 1},
            file_asserts={
                "redbark_transactions_2025.csv": [
                    assert_file_column_values("Vetted", ["Yes", "Yes", "Yes", None, "No", "No"], sort_by=["Description"]),
                    assert_file_column_values("Category Manual", [None, "Clothing", "Clothing", None, None, "Clothing"], sort_by=["Description"]),
                ],
                "__bank_logs.csv": [assert_file_column_values("Code", ["TRANSACTIONS_UNVETTED", "TRANSACTION_VETTED"], sort_by=["Code"])],
            },
        )

    # A reprocess re-derives every row, a moved row losing its tick, a manual category keeping it
    def test_bank_local_partial_41(self):
        self._bank_run(
            "partial_41",
            standing=2,
            rerun=False,
            force=True,
            file_asserts={
                "redbark_transactions_2025.csv": [
                    assert_file_column_values("Category Auto", [None] * 9 + ["Groceries", "Groceries"], sort_by=["Description"]),
                    assert_file_column_values("Vetted", [None] * 10 + ["Yes"], sort_by=["Description"]),
                ],
            },
        )

    # Files in an earlier column order and amount format are rewritten in the current form by a reprocess that changes none of their rows
    def test_bank_local_partial_67(self):
        self._bank_run(
            "partial_67",
            rerun=False,
            force=True,
            file_asserts={
                "redbark_transactions_2025.csv": [
                    assert_file_columns(list(TRANSACTIONS_SCHEMA)),
                    assert_file_column_values("Amount", ["-1.00"], raw=True),
                    assert_file_column_values("Amount Split", ["-1.00"], raw=True),
                    assert_file_column_values("Category Auto", ["Groceries"]),
                    assert_file_column_values("Vetted", ["Yes"]),
                ],
                "redbark_balances_2025.csv": [
                    assert_file_column_values("Balance", ["11.00"], raw=True),
                    assert_file_column_values("Balance Auto", ["11.00"], raw=True),
                ],
            },
        )

    # A held description and a note holding spreadsheet error values are each raised as a standing warning, the rows kept
    def test_bank_local_partial_68(self):
        self._bank_run(
            "partial_68",
            file_asserts={
                "redbark_transactions_2025.csv": [assert_file_size(min_rows=3, max_rows=3)],
                "__bank_logs.csv": [
                    assert_file_column_values("Code", ["TRANSACTION_SPREADSHEET_ERROR"] * 2),
                    assert_file_column_values("Kind", [plugin.LOG_KIND_WARNING] * 2),
                ],
            },
        )

    # A classifier edit re-derives every row, each cleared tick logged once
    def test_bank_local_partial_47(self):
        self._bank_run(
            "partial_47",
            standing=2,
            file_asserts={
                "redbark_transactions_2025.csv": [
                    assert_file_column_values("Category Auto", ["Restaurants"] * 3 + [None] * 11 + ["Groceries"], sort_by=["Description"]),
                    assert_file_column_values("Vetted", [None, "No", "Yes"] + [None] * 11 + ["Yes"], sort_by=["Description"]),
                ],
                "bank_reclassified_2026_01.csv": [
                    assert_file_column_values("Description", ["Cafe One", "Gone One"], sort_by=["Description"]),
                    assert_file_column_values("Source", ["classifier"] * 2, sort_by=["Description"]),
                    assert_file_column_values("Auto Before", ["Food"] * 2, sort_by=["Description"]),
                    assert_file_column_values("Auto After", ["Restaurants", None], sort_by=["Description"]),
                    assert_file_column_values("Vetted Before", ["Yes", "Yes"], sort_by=["Description"]),
                    assert_file_column_values("Vetted After", [None, None], sort_by=["Description"]),
                    assert_file_nones_per_col(include=r"File MD5"),
                ],
                "bank_reclassified_2025_12.csv": [assert_file_size(min_rows=1, max_rows=1)],
                "__bank_classifier.csv": [assert_file_column_values("Category", ["Groceries", "Food", "Restaurants"])],
                "__bank_logs.csv": [assert_file_column_values("Code", ["TRANSACTIONS_UNCLASSIFIED", "TRANSACTIONS_UNVETTED"], sort_by=["Code"])],
            },
        )

    # An unchanged classifier leaves a category no rule produces on a standard run
    def test_bank_local_partial_48(self):
        self._bank_run(
            "partial_48",
            standing=2,
            rerun=False,
            file_asserts={
                "redbark_transactions_2025.csv": [
                    assert_file_column_values("Category Auto", [None] * 4 + ["Legacy", "Groceries"], sort_by=["Description"]),
                    assert_file_column_values("Vetted", [None] * 4 + ["Yes", "Yes"], sort_by=["Description"]),
                ],
                "bank_reclassified_2026_01.csv": [assert_file_does_not_exist()],
            },
        )

    # An unchanged classifier blanks a category no rule produces on a reprocess, logging the change
    def test_bank_local_partial_57(self):
        self._bank_run(
            "partial_57",
            standing=2,
            rerun=False,
            force=True,
            file_asserts={
                "redbark_transactions_2025.csv": [
                    assert_file_column_values("Category Auto", [None] * 5 + ["Groceries"], sort_by=["Description"]),
                    assert_file_column_values("Vetted", [None] * 5 + ["Yes"], sort_by=["Description"]),
                ],
                "bank_reclassified_2026_01.csv": [
                    assert_file_column_values("Description", ["Old One"]),
                    assert_file_column_values("Auto Before", ["Legacy"]),
                    assert_file_column_values("Auto After", [None]),
                    assert_file_column_values("Vetted After", [None]),
                ],
            },
        )

    # A classifier edit with a pattern in two categories is held, rows classified by the last applied tab
    def test_bank_local_corrupt_33(self):
        self._bank_run(
            "corrupt_33",
            standing=2,
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 2},
            file_asserts={
                "redbark_transactions_2025.csv": [
                    assert_file_column_values("Category Auto", ["Food"] + [None] * 3 + ["Food", "Groceries"], sort_by=["Description"]),
                    assert_file_column_values("Vetted", ["Yes"] + [None] * 4 + ["Yes"], sort_by=["Description"]),
                ],
                "__bank_classifier.csv": [assert_file_column_values("Category", ["Food", "Groceries"])],
                "__bank_logs.csv": [
                    assert_file_column_values(
                        "Code",
                        ["CLASSIFIER_HELD", "CLASSIFIER_PATTERN_CONFLICT", "TRANSACTIONS_UNCLASSIFIED", "TRANSACTIONS_UNVETTED"],
                        sort_by=["Code"],
                    )
                ],
            },
        )

    # A held classifier edit stays held on a reprocess
    def test_bank_local_corrupt_35(self):
        self._bank_run(
            "corrupt_35",
            standing=2,
            rerun=False,
            force=True,
            errored={plugin.CTR_SRC_SOURCES: 2},
            file_asserts={
                "redbark_transactions_2025.csv": [
                    assert_file_column_values("Category Auto", ["Food"] + [None] * 3 + ["Food", "Groceries"], sort_by=["Description"]),
                    assert_file_column_values("Vetted", ["Yes"] + [None] * 4 + ["Yes"], sort_by=["Description"]),
                ],
                "__bank_classifier.csv": [assert_file_column_values("Category", ["Food", "Groceries"])],
                "__bank_logs.csv": [
                    assert_file_column_values(
                        "Code",
                        ["CLASSIFIER_HELD", "CLASSIFIER_PATTERN_CONFLICT", "TRANSACTIONS_UNCLASSIFIED", "TRANSACTIONS_UNVETTED"],
                        sort_by=["Code"],
                    )
                ],
            },
        )

    # A bucket only classifier edit clears no tick and regroups the closed month's totals
    def test_bank_local_partial_49(self):
        self._bank_run(
            "partial_49",
            standing=2,
            file_asserts={
                "redbark_transactions_2025.csv": [assert_file_column_values("Vetted", ["Yes"] * 2 + [None] * 6 + ["Yes"] * 2, sort_by=["Description"])],
                "bank_reclassified_2026_01.csv": [assert_file_does_not_exist()],
                "_sheet_bank_transactions.csv": [
                    assert_file_column_values("Bucket", [None, "Discretionary", "Living", "Discretionary", "Living"]),
                    assert_file_column_values("Category", [None, None, None, "Food", "Groceries"]),
                    assert_file_column_values("Total", ["12.0", "8.0", "4.0", "8.0", "4.0"]),
                ],
            },
        )

    # Files changed on Drive are reclassified without a reprocess, each change logged by its source
    def test_bank_local_partial_50(self):
        self._bank_run(
            "partial_50",
            standing=3,
            sheet_downloads=1,
            file_asserts={
                "redbark_transactions_2025.csv": [
                    assert_file_column_values("Category Auto", ["Food"] + [None] * 4 + ["Groceries"], sort_by=["Description"]),
                    assert_file_column_values("Vetted", ["Yes"] + [None] * 5, sort_by=["Description"]),
                ],
                "manual_transactions_2025.csv": [
                    assert_file_column_values("Description", ["Shop Three"]),
                    assert_file_column_values("Category Auto", ["Groceries"]),
                ],
                "bank_reclassified_2026_01.csv": [
                    assert_file_column_values("Source", ["classifier", "sheet"], sort_by=["Source", "Description"]),
                    assert_file_column_values("Description", ["Shop Two", "Shop Two"], sort_by=["Source", "Description"]),
                    assert_file_column_values("Vetted After", [None, "Yes"], sort_by=["Source", "Description"]),
                    assert_file_column_values("Auto After", ["Groceries", None], sort_by=["Source", "Description"]),
                ],
            },
        )

    # A stale tab cannot re-tick a moved row but can untick one, a manual category edit keeps its tick, only edits logged
    def test_bank_local_partial_51(self):
        self._bank_run(
            "partial_51",
            standing=2,
            sheet_downloads=1,
            file_asserts={
                "redbark_transactions_2025.csv": [
                    assert_file_column_values("Vetted", [None] * 4 + ["Yes", "Yes", None, None], sort_by=["Description"]),
                    assert_file_column_values("Category Manual", [None] * 4 + ["Groceries", "Food", None, None], sort_by=["Description"]),
                ],
                "bank_reclassified_2026_01.csv": [
                    assert_file_column_values("Description", ["Shop A", "Shop B", "Shop D"], sort_by=["Description"]),
                    assert_file_column_values("Source", ["sheet"] * 3, sort_by=["Description"]),
                    assert_file_column_values("Vetted After", ["Yes", "Yes", None], sort_by=["Description"]),
                ],
            },
        )

    # A replaced card shares its name with the closed card it replaced without error
    def test_bank_local_partial_38(self):
        self._bank_run(
            "partial_38",
            file_asserts={
                "__bank_transactions_current.csv": [assert_file_size(min_rows=2, max_rows=2), assert_file_column_distinct("Account ID", 2)],
                "__bank_logs.csv": [assert_file_size(min_rows=0, max_rows=0)],
            },
        )

    # Two open cards sharing a name on one date are a source error
    def test_bank_local_corrupt_31(self):
        self._bank_run(
            "corrupt_31",
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "__bank_logs.csv": [assert_file_column_values("Code", ["ACCOUNT_NAME_SHARED"])],
            },
        )

    # A transaction held on both a closed card and its replacement is one standing warning
    def test_bank_local_partial_39(self):
        self._bank_run(
            "partial_39",
            file_asserts={
                "__bank_transactions_current.csv": [assert_file_size(min_rows=3, max_rows=3)],
                "__bank_logs.csv": [
                    assert_file_column_values("Code", ["TRANSACTION_TWO_ACCOUNTS"]),
                    assert_file_column_values("Tab", ["Transactions_2026"]),
                ],
            },
        )

    # A header only accounts tab is filled from Redbark and its balances stored on the same run
    def test_bank_local_partial_42(self):
        self._bank_run(
            "partial_42",
            source=True,
            rerun=False,
            file_asserts={
                "_sheet_bank_accounts.csv": [
                    assert_file_column_values("Name", ["Raw One", "Raw Two"]),
                    assert_file_column_values("Status", ["Linked", "Linked"]),
                    assert_file_column_values("Type", ["Asset", "Liability"]),
                    assert_file_column_values("Redbark Account ID", ["a1", "a2"]),
                ],
                "__bank_balances_current.csv": [assert_file_size(min_rows=2, max_rows=2)],
            },
        )

    # Two identical transactions, one given a category manual, each keep their own id
    def test_bank_local_partial_43(self):
        self._bank_run(
            "partial_43",
            sheet_downloads=1,
            file_asserts={
                "redbark_transactions_2025.csv": [
                    assert_file_column_values("Category Manual", ["Clothing", None], sort_by=["Source ID"]),
                    assert_file_column_values("Transaction ID", ["a8c61ffc86d3546db806c31b4a8cece7", "92dbf60c4d6f5860873b6c28342ca850"], sort_by=["Source ID"]),
                ],
            },
        )

    # A short merchant code is padded and two transactions sharing a Redbark id are rejected
    def test_bank_local_partial_44(self):
        self._bank_run(
            "partial_44",
            source=True,
            rerun=False,
            file_asserts={
                "redbark_transactions_2026.csv": [assert_file_column_values("Source ID", ["t1"]), assert_file_column_values("Merchant Code", ["0812"], raw=True)],
                "__bank_logs.csv": [assert_file_column_values("Code", ["TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED_CURRENT", "TRANSACTION_RESPONSE"], sort_by=["Code"])],
            },
        )

    # Two identical history transactions keep distinct pinned ids by ordinal
    def test_bank_local_partial_10(self):
        self._bank_run(
            "partial_10",
            rerun=False,
            force=True,
            counters={plugin.CTR_SRC_FILES: {plugin.CTR_ACT_PROCESSED: 1}},
            file_asserts={
                "__bank_transactions_current.csv": [
                    assert_file_size(min_rows=3, max_rows=3),
                    assert_file_column_values(
                        "Transaction ID", ["0c44da25a5f9513cb483b7cd368d8921", "2ba8c1c0858c5d51abe091996e496dc8", "4e78230a0c5e57a697d68c42c10b59be"], sort_by=["Transaction ID"]
                    ),
                ],
            },
        )

    # Split parts are derived on read and share one id
    def test_bank_local_partial_15(self):
        self._bank_run(
            "partial_15",
            rerun=False,
            force=True,
            file_asserts={
                "__bank_transactions_current.csv": [
                    assert_file_size(min_rows=3, max_rows=3),
                    assert_file_column_values("Split", ["0", "1", "2"], sort_by=["Split"]),
                    assert_file_column_values("Category", [None, "Car", "Groceries"], sort_by=["Split"]),
                    assert_file_column_distinct("Transaction ID", 2),
                ],
            },
        )

    # An unreadable year file errors the file and holds its year, another year commits
    def test_bank_local_corrupt_15(self):
        self._bank_run(
            "corrupt_15",
            standing=2,
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 1, plugin.CTR_SRC_FILES: 1},
            file_asserts={
                "redbark_transactions_2026.csv": [assert_file_does_exist()],
                "__bank_transactions_current.csv": [assert_file_size(min_rows=1, max_rows=1), assert_file_dates(start_date="2025-12-03", end_date="2025-12-03")],
            },
        )

    # Manual balances on Drive are given account ids and carried to linked moments
    def test_bank_local_partial_21(self):
        self._bank_run(
            "partial_21",
            file_asserts={
                "manual_balances_2026.csv": [
                    assert_file_column_values("Balance Manual", ["101.0", "105.0", "110.0"], sort_by=["Date"]),
                    assert_file_column_values("Time", ["23:59:59", "09:00:00", "23:59:59"], sort_by=["Date"]),
                    assert_file_column_values("Account ID", ["6ec277688b3c570982242484009c9cdb"] * 3),
                ],
                "manual_balances_2025.csv": [assert_file_size(min_rows=0, max_rows=0), assert_file_columns(list(BALANCES_SCHEMA))],
                "__bank_balances_current.csv": [
                    assert_file_size(min_rows=6, max_rows=6),
                    assert_file_column_values("Balance", ["101.0", "101.0", "10.0", "105.0", "12.0", "110.0"], sort_by=["Date", "Time", "Account"]),
                ],
            },
        )

    # A manual balances file with invalid rows is left as is and its year held
    def test_bank_local_corrupt_20(self):
        self._bank_run(
            "corrupt_20",
            standing=1,
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 4},
            file_asserts={
                "manual_balances_2026.csv": [assert_file_size(min_rows=5, max_rows=5), assert_file_columns(["Date", "Time", "Account", "Balance Manual"])],
                "__bank_balances_current.csv": [assert_file_does_not_exist()],
                "__bank_logs.csv": [assert_file_column_values("Code", ["ACCOUNT_LINKED", "ACCOUNT_NOT_MANUAL", "BALANCE_MANUAL_STALE", "DATE_FUTURE", "VALUE_UNPARSED"], sort_by=["Code"])],
            },
        )

    # Manual transactions on Drive are given account ids and splits and moved to their year file
    def test_bank_local_partial_22(self):
        self._bank_run(
            "partial_22",
            file_asserts={
                "manual_transactions_2026.csv": [
                    assert_file_column_values("Description", ["Tip", "Snack", "Lunch", "Dinner"], sort_by=["Date"]),
                    assert_file_column_values("Amount Split", ["-3.0", "-5.0", "-10.0", "-1030.0"], sort_by=["Date"]),
                    assert_file_nones_per_col(include=r"Account ID|Transaction ID"),
                ],
                "manual_transactions_2025.csv": [assert_file_size(min_rows=0, max_rows=0), assert_file_columns(list(TRANSACTIONS_SCHEMA))],
                "__bank_transactions_current.csv": [
                    assert_file_size(min_rows=5, max_rows=5),
                    assert_file_column_values("Description", ["Tip", "Snack", "Lunch", "Coffee", "Dinner"], sort_by=["Date"]),
                ],
                "_sheet_bank_transactions_2026.csv": [assert_file_size(min_rows=5, max_rows=5)],
            },
        )

    # Tab edits outside the editable columns are rejected and put back
    def test_bank_local_corrupt_21(self):
        self._bank_run(
            "corrupt_21",
            sheet_downloads=1,
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 3},
            file_asserts={
                "redbark_transactions_2026.csv": [assert_file_column_values("Description", ["Coffee", "Fee"], sort_by=["Date"])],
                "_sheet_bank_transactions_2026.csv": [assert_file_size(min_rows=2, max_rows=2)],
                "__bank_logs.csv": [
                    assert_file_column_values("Code", ["SPLIT_INVALID", "TAB_EDIT_IGNORED", "TAB_EDIT_IGNORED", "TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED_CURRENT"], sort_by=["Code"])
                ],
            },
        )

    # A manual row dated in a year whose file is unreadable holds both years
    def test_bank_local_corrupt_32(self):
        self._bank_run(
            "corrupt_32",
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 2, plugin.CTR_SRC_FILES: 1},
            file_asserts={
                "manual_transactions_2026.csv": [assert_file_columns(["Date", "Account", "Amount", "Description"])],
                "manual_transactions_2025.csv": [assert_file_does_exist()],
                "__bank_transactions_current.csv": [assert_file_does_not_exist()],
                "__bank_logs.csv": [assert_file_column_values("Tab", ["manual_transactions_2025.csv", "manual_transactions_2026.csv"], sort_by=["Tab"])],
            },
        )

    # A category manual and a valid split on linked rows are kept
    def test_bank_local_partial_23(self):
        self._bank_run(
            "partial_23",
            sheet_downloads=1,
            file_asserts={
                "redbark_transactions_2026.csv": [
                    assert_file_size(min_rows=3, max_rows=3),
                    assert_file_column_values("Category Manual", ["Groceries", "Car", "Groceries"], sort_by=["Amount Split"]),
                ],
                "__bank_transactions_current.csv": [
                    assert_file_column_values("Split", ["2", "1", "0"], sort_by=["Amount Split"]),
                    assert_file_column_values("Bucket", ["Living", "Maintenance", "Living"], sort_by=["Amount Split"]),
                    assert_file_column_distinct("Transaction ID", 2),
                ],
            },
        )

    # Classification by longest pattern, then merchant code, then bank code
    def test_bank_local_partial_24(self):
        self._bank_run(
            "partial_24",
            file_asserts={
                "redbark_transactions_2026.csv": [
                    assert_file_column_values(
                        "Category Auto",
                        ["Groceries", "Restaurants", "Groceries", "Restaurants", None, "Shopping", None, "Groceries", "Restaurants", None, None, None, None, None, None],
                        sort_by=["Date", "Amount"],
                    ),
                    assert_file_column_values("Vetted", [None] * 8 + ["Yes"] + [None] * 6, sort_by=["Date", "Amount"]),
                ],
                "__bank_transactions_current.csv": [
                    assert_file_column_values(
                        "Category",
                        ["Groceries", "Restaurants", "Groceries", "Restaurants", None, "Shopping", None, "Groceries", "Groceries", None, None, None, None, None, None],
                        sort_by=["Date", "Amount"],
                    ),
                ],
            },
        )

    # Classifier code and tie errors hold the edit, with no applied tab nothing is classified
    def test_bank_local_corrupt_22(self):
        self._bank_run(
            "corrupt_22",
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 4},
            file_asserts={
                "redbark_transactions_2026.csv": [assert_file_column_values("Category Auto", [None] * 7)],
                "__bank_logs.csv": [
                    assert_file_column_values(
                        "Code",
                        [
                            "CLASSIFIER_BANK_CODE",
                            "CLASSIFIER_CODE_ROWS",
                            "CLASSIFIER_HELD",
                            "CLASSIFIER_MERCHANT_CODE",
                            "CLASSIFIER_TIE",
                            "TRANSACTIONS_UNCLASSIFIED_CURRENT",
                            "TRANSACTIONS_UNVETTED_CURRENT",
                        ],
                        sort_by=["Code"],
                    )
                ],
            },
        )

    # The plugin's own uploads read back as no edit
    def test_bank_local_partial_25(self):
        self._bank_run(
            "partial_25",
            standing=2,
            sheet_downloads=99,
            file_asserts={
                "_sheet_bank_balances.csv": [assert_file_does_exist()],
                "_sheet_bank_transactions_2026.csv": [assert_file_size(min_rows=5, max_rows=5)],
                "_sheet_bank_transactions_2025.csv": [assert_file_size(min_rows=1, max_rows=1)],
                "_sheet_bank_transactions.csv": [assert_file_does_not_exist()],
            },
        )

    # A tab edited between the read and the upload is skipped, later tabs upload
    def test_bank_local_partial_26(self):
        self._bank_run(
            "partial_26",
            sheet_downloads=0,
            rerun=False,
            file_asserts={
                "_sheet_bank_balances.csv": [assert_file_column_values("Balance Auto", ["10.0"])],
                "_sheet_bank_transactions_2026.csv": [assert_file_size(min_rows=1, max_rows=1)],
                "__bank_balances_current.csv": [assert_file_size(min_rows=1, max_rows=1)],
            },
        )

    # A reprocess dedupes transactions by source id, genuine repeats kept
    def test_bank_local_partial_27(self):
        self._bank_run(
            "partial_27",
            standing=1,
            rerun=False,
            force=True,
            errored={plugin.CTR_SRC_DATA: 1},
            file_asserts={
                "redbark_transactions_2025.csv": [assert_file_size(min_rows=1, max_rows=1)],
                "redbark_transactions_2026.csv": [
                    assert_file_size(min_rows=6, max_rows=6),
                    assert_file_column_values("Description", ["History", "Live", "Split", "Split", "Same", "Same"], sort_by=["Date", "Amount Split"]),
                ],
                "__bank_logs.csv": [
                    assert_file_column_values(
                        "Code", ["DEDUPE_REMOVED", "TRANSACTIONS_UNCLASSIFIED", "TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED", "TRANSACTIONS_UNVETTED_CURRENT"], sort_by=["Code"]
                    )
                ],
            },
        )

    # A sweep re-dates a never dated transaction into a later year's file once
    def test_bank_local_partial_45(self):
        self._bank_run(
            "partial_45",
            source=True,
            rerun=False,
            file_asserts={
                "redbark_transactions_2025.csv": [assert_file_size(min_rows=0, max_rows=0)],
                "redbark_transactions_2026.csv": [
                    assert_file_column_values("Source ID", ["t1", "t9"], sort_by=["Date"]),
                    assert_file_column_values("Date Posted", ["2026-01-05", "2026-01-10"], sort_by=["Date"]),
                ],
                "__bank_transactions_current.csv": [assert_file_size(min_rows=2, max_rows=2)],
                "__bank_logs.csv": [assert_file_column_values("Code", ["TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED_CURRENT"], sort_by=["Code"])],
            },
        )

    # A relisted transaction is adopted, an unlisted one kept, a never dated one takes Redbark's dates
    def test_bank_local_partial_52(self):
        self._bank_run(
            "partial_52",
            source=True,
            rerun=False,
            file_asserts={
                "redbark_transactions_2026.csv": [
                    assert_file_size(min_rows=4, max_rows=4),
                    assert_file_column_values("Source ID", ["t4", "t1b", "t3", "t2"], sort_by=["Date"]),
                    assert_file_column_values("Date", ["2026-01-06", "2026-01-08", "2026-01-09", "2026-01-12"], sort_by=["Date"]),
                    assert_file_column_values("Date Posted", ["2026-01-07", "2026-01-09", "2026-01-11", "2026-01-12"], sort_by=["Date"]),
                ],
                "__bank_logs.csv": [
                    assert_file_column_values(
                        "Code",
                        ["TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED_CURRENT", "TRANSACTION_GONE", "TRANSACTION_RELISTED"],
                        sort_by=["Code"],
                    )
                ],
            },
        )

    # A forced download dates held history, adds what Redbark lists across the whole history and reports what it no longer lists
    def test_bank_local_partial_53(self):
        self._bank_run(
            "partial_53",
            standing=2,
            source=True,
            rerun=False,
            downloads=True,
            file_asserts={
                "redbark_transactions_2025.csv": [
                    assert_file_column_values("Source ID", ["t5", "t7", "t8"], sort_by=["Date"]),
                    assert_file_column_values("Date", ["2025-06-09", "2025-07-01", "2025-08-01"], sort_by=["Date"]),
                    assert_file_column_values("Date Posted", ["2025-06-10", "2025-07-02", "2025-08-02"], sort_by=["Date"]),
                ],
                "redbark_transactions_2026.csv": [assert_file_column_values("Source ID", ["t6"])],
                "__bank_logs.csv": [
                    assert_file_column_values(
                        "Code", ["TRANSACTIONS_UNCLASSIFIED", "TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED", "TRANSACTIONS_UNVETTED_CURRENT", "TRANSACTION_GONE"], sort_by=["Code"]
                    ),
                    assert_file_column_values("Key", ["2025", "2026", "2025", "2026", "t8"], sort_by=["Code"]),
                ],
            },
        )

    # A linked balance moving more than its transactions explain is unreconciled once
    def test_bank_local_partial_54(self):
        self._bank_run(
            "partial_54",
            standing=3,
            rerun=False,
            file_asserts={
                "__bank_logs.csv": [
                    assert_file_column_values(
                        "Code",
                        ["BALANCE_UNRECONCILED", "TRANSACTIONS_UNCLASSIFIED", "TRANSACTIONS_UNVETTED"],
                        sort_by=["Code"],
                    ),
                    assert_file_column_values("Key", ["One 2025-12-24", "2025", "2025"], sort_by=["Code"]),
                ],
            },
        )

    # An HSBC transaction is dated by its Sydney day, other banks by Redbark's date
    def test_bank_local_partial_55(self):
        self._bank_run(
            "partial_55",
            source=True,
            rerun=False,
            file_asserts={
                "redbark_transactions_2026.csv": [
                    assert_file_column_values("Source ID", ["b1", "h1", "h2", "h3"], sort_by=["Source ID"]),
                    assert_file_column_values("Date", ["2026-01-05", "2026-01-06", "2026-01-08", "2026-01-09"], sort_by=["Source ID"]),
                    assert_file_column_values("Date Posted", ["2026-01-05", "2026-01-06", "2026-01-08", "2026-01-09"], sort_by=["Source ID"]),
                ],
            },
        )

    # An HSBC transaction held on the check window's first day is not gone, one a day later Redbark no longer lists is
    def test_bank_local_partial_70(self):
        self._bank_run(
            "partial_70",
            source=True,
            rerun=False,
            file_asserts={
                "redbark_transactions_2026.csv": [assert_file_column_values("Source ID", ["h1", "h2", "h3"], sort_by=["Date"])],
                "__bank_logs.csv": [
                    assert_file_column_values("Code", ["TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED_CURRENT", "TRANSACTION_GONE"], sort_by=["Code"]),
                    assert_file_column_values("Key", ["2026", "2026", "h2"], sort_by=["Code"]),
                ],
            },
        )

    # A card's import carries its last balance to today, one without a reading carries none and stays stale, and the unmoved carried balance is a current month warning
    def test_bank_local_partial_71(self):
        self._bank_run(
            "partial_71",
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 1},
            file_asserts={
                "manual_balances_2026.csv": [
                    assert_file_column_values("Account", ["Card", "Card"], sort_by=["Date", "Account"]),
                    assert_file_column_values("Date", ["2026-01-10", "2026-01-15"], sort_by=["Date", "Account"]),
                    assert_file_column_values("Balance Manual", ["-100.0", "-100.0"], sort_by=["Date", "Account"]),
                ],
                "__bank_logs.csv": [
                    assert_file_column_values("Code", ["BALANCE_MANUAL_STALE", "BALANCE_UNRECONCILED_CURRENT", "TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED_CURRENT"], sort_by=["Code"]),
                    assert_file_column_values("Key", ["Other Card", "Card 2026-01-15", "2026", "2026"], sort_by=["Code"]),
                ],
            },
        )

    # An Accounts tab with a duplicate row leaves a year tab's edits unmerged, the tab not uploaded over them and its base kept
    def test_bank_local_partial_75(self):
        self._bank_run(
            "partial_75",
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "redbark_transactions_2026.csv": [assert_file_column_values("Vetted", ["Yes", "Yes", None, None, None, None], sort_by=["Date"])],
                "_sheet_bank_transactions_2026_v1.csv": [assert_file_does_not_exist()],
                "__bank_tab_transactions_2026.csv": [assert_file_column_values("Vetted", [None, None, None, None, "Yes", "Yes"])],
                "__bank_logs.csv": [assert_file_column_values("Code", ["TAB_UNUSABLE", "TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED_CURRENT"], sort_by=["Code"])],
            },
        )

    # An Accounts tab with a duplicate row holds a changed manual file's year unchecked, nothing committed
    def test_bank_local_partial_76(self):
        self._bank_run(
            "partial_76",
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "manual_transactions_2026.csv": [assert_file_column_values("Vetted", ["Yse"])],
                "__bank_transactions_current.csv": [assert_file_does_not_exist()],
                "__bank_committed.json": [assert_file_does_not_exist()],
            },
        )

    # A manual balance dated outside its file's year is an error holding the file's year, its account then without a reading
    def test_bank_local_partial_77(self):
        self._bank_run(
            "partial_77",
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 2},
            file_asserts={
                "__bank_balances_current.csv": [assert_file_does_not_exist()],
                "__bank_logs.csv": [assert_file_column_values("Code", ["BALANCE_MANUAL_STALE", "DATE_YEAR"], sort_by=["Code"])],
            },
        )

    # An export spanning a year whose manual file is unreadable imports the other year but is not recorded as imported
    def test_bank_local_partial_78(self):
        def _export_unrecorded(_first, _second, _third, local_cache=""):
            with open(join(local_cache, "__bank_committed.json")) as committed_file:
                recorded = sorted(json.load(committed_file))
            return None if recorded == ["manual_balances_2026.csv", "manual_transactions_2026.csv"] else f"recorded [{', '.join(recorded)}]"

        self._bank_run(
            "partial_78",
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 2, plugin.CTR_SRC_FILES: 1},
            custom_asserts=[_export_unrecorded],
            file_asserts={
                "manual_transactions_2026.csv": [assert_file_column_values("Description", ["CAFE ONE"])],
                "__bank_logs.csv": [
                    assert_file_column_values("Code", ["FILE_UNREADABLE", "FILE_UNREADABLE", "TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED_CURRENT"], sort_by=["Code"]),
                    assert_file_column_values("Tab", ["Transactions_2026", "Transactions_2026", "amex_xxxx0002_transactions_2026-01-14.csv", "manual_transactions_2025.csv"], sort_by=["Tab"]),
                ],
            },
        )

    # A reprocess with an invalid manual file of the year before keeps that year's committed transactions and balances
    def test_bank_local_partial_79(self):
        self._bank_run(
            "partial_79",
            rerun=False,
            force=True,
            errored={plugin.CTR_SRC_DATA: 2},
            file_asserts={
                "__bank_transactions_current.csv": [assert_file_column_values("Date", ["2025-11-04", "2026-01-03"], sort_by=["Date"])],
                "__bank_balances_current.csv": [assert_file_column_values("Date", ["2025-11-30", "2026-01-10"], sort_by=["Date"])],
            },
        )

    # A manual file not in UTF-8 is unreadable and holds its year, the run not stopped renaming columns
    def test_bank_local_corrupt_43(self):
        self._bank_run(
            "corrupt_43",
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 1, plugin.CTR_SRC_FILES: 1},
            file_asserts={
                "manual_transactions_2026.csv": [assert_file_does_exist()],
                "__bank_transactions_current.csv": [assert_file_does_not_exist()],
                "__bank_logs.csv": [assert_file_column_values("Code", ["FILE_UNREADABLE"])],
            },
        )

    # A manual file whose rows move into a file itself held by an unreadable year is held in turn
    def test_bank_local_corrupt_44(self):
        self._bank_run(
            "corrupt_44",
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 3, plugin.CTR_SRC_FILES: 1},
            file_asserts={
                "manual_transactions_2024.csv": [assert_file_column_values("Description", ["Snack"])],
                "manual_transactions_2025.csv": [assert_file_column_values("Description", ["Coffee"])],
                "__bank_transactions_current.csv": [assert_file_does_not_exist()],
                "__bank_logs.csv": [assert_file_column_values("Tab", ["manual_transactions_2024.csv", "manual_transactions_2025.csv", "manual_transactions_2026.csv"], sort_by=["Tab"])],
            },
        )

    # A manual balance edited on the Balances tab is written to its file, a linked balance edit put back
    def test_bank_local_partial_72(self):
        self._bank_run(
            "partial_72",
            standing=2,
            rerun=False,
            file_asserts={
                "manual_balances_2026.csv": [assert_file_column_values("Balance Manual", ["-125.5"])],
                "redbark_balances_2026.csv": [assert_file_column_values("Balance Auto", ["10.0"])],
                "__bank_logs.csv": [assert_file_column_values("Code", ["BALANCE_MANUAL_STALE", "TAB_EDIT_IGNORED"], sort_by=["Code"])],
            },
        )

    # A break into a closed month and a closed month without a balance are errors, a break in the current month a warning
    def test_bank_local_partial_73(self):
        self._bank_run(
            "partial_73",
            standing=5,
            rerun=False,
            file_asserts={
                "__bank_logs.csv": [
                    assert_file_column_values(
                        "Code",
                        [
                            "BALANCE_MANUAL_STALE",
                            "BALANCE_MANUAL_STALE",
                            "BALANCE_UNRECONCILED",
                            "BALANCE_UNRECONCILED_CURRENT",
                            "TRANSACTIONS_UNCLASSIFIED",
                            "TRANSACTIONS_UNCLASSIFIED_CURRENT",
                            "TRANSACTIONS_UNVETTED",
                            "TRANSACTIONS_UNVETTED_CURRENT",
                        ],
                        sort_by=["Code"],
                    ),
                    assert_file_column_values("Key", ["Card 2025-12", "Other Card", "Card 2025-10-31", "Card 2026-01-10", "2025", "2026", "2025", "2026"], sort_by=["Code", "Key"]),
                ],
            },
        )

    # Files written before the derived and linked columns were renamed auto are renamed in place, every value kept
    def test_bank_local_partial_74(self):
        self._bank_run(
            "partial_74",
            standing=1,
            rerun=False,
            file_asserts={
                "redbark_balances_2026.csv": [assert_file_columns(list(BALANCES_SCHEMA)), assert_file_column_values("Balance Auto", ["10.0"])],
                "manual_balances_2026.csv": [assert_file_columns(list(BALANCES_SCHEMA)), assert_file_column_values("Balance Manual", ["-50.0"])],
                "redbark_transactions_2026.csv": [assert_file_columns(list(TRANSACTIONS_SCHEMA)), assert_file_column_values("Category Auto", ["Groceries"])],
                "bank_reclassified_2026_01.csv": [assert_file_column_values("Auto Before", ["Restaurants"]), assert_file_column_values("Auto After", ["Groceries"])],
            },
        )

    # Closed month totals described, a category by its Classifier description, a bucket by its categories, a month by its buckets, a pattern row description a warning
    def test_bank_local_partial_69(self):
        self._bank_run(
            "partial_69",
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 2},
            file_asserts={
                "_sheet_bank_transactions.csv": [
                    assert_file_column_values("Category", [None] * 6 + ["Restaurants", "Groceries", "Fuel", "Groceries", "Pharmacy", "Car RAC"]),
                    assert_file_column_values("Total", ["30.0", "445.0", "50.0", "-20.0", "145.0", "300.0", "50.0", "-20.0", "40.0", "100.0", "5.0", "300.0"]),
                    assert_file_column_values(
                        "Description",
                        [
                            "Includes discretionary & living buckets this month",
                            "Includes living & maintenance buckets this month",
                            "Includes the restaurants category this month",
                            "Includes the groceries category this month",
                            "Includes fuel, groceries & pharmacy categories this month",
                            "Includes the car RAC category this month",
                            None,
                            "Includes supermarkets & bakeries this month",
                            "Includes petrol & diesel this month",
                            "Includes supermarkets & bakeries this month",
                            "Includes medicines this month",
                            "Includes servicing & repairs this month",
                        ],
                    ),
                ],
                "__bank_logs.csv": [assert_file_column_values("Code", ["CLASSIFIER_DESCRIPTION", "TRANSACTIONS_UNCLASSIFIED", "TRANSACTIONS_UNVETTED"], sort_by=["Code"])],
            },
        )

    # Closed month totals on the Transactions tab, month then bucket then category, skipping unvetted, uncategorised and current months and the excluded bucket
    def test_bank_local_partial_28(self):
        self._bank_run(
            "partial_28",
            standing=2,
            file_asserts={
                "_sheet_bank_transactions.csv": [
                    assert_file_columns(["End of Month", "Bucket", "Category", "Total", "Description"]),
                    assert_file_column_values("End of Month", ["2026-01-01", "2025-11-01"] + ["2026-01-01"] * 2 + ["2025-11-01"] * 2 + ["2026-01-01"] * 2 + ["2025-11-01"] * 2),
                    assert_file_column_values("Bucket", [None, None, "Discretionary", "Living", "Living", "Maintenance", "Discretionary", "Living", "Living", "Maintenance"]),
                    assert_file_column_values("Category", [None] * 6 + ["Restaurants", "Groceries", "Groceries", "Car"]),
                    assert_file_column_values("Total", ["30.0", "400.0", "50.0", "-20.0", "100.0", "300.0", "50.0", "-20.0", "100.0", "300.0"]),
                ],
            },
        )

    # The logs tab lists errors then warnings newest first, a kept problem a run no longer raises historic and a warning for thirty days from its date raised, any other dropped
    def test_bank_local_partial_29(self):
        self._bank_run(
            "partial_29",
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "_sheet_bank_logs.csv": [
                    assert_file_columns(["Date", "Time", "Date Raised", "Kind", "State", "Counter", "Tab", "Key", "Code", "Detail"]),
                    assert_file_column_values("Code", ["ACCOUNT_UNMAPPED", "TRANSACTION_GONE", "BALANCE_UNRECONCILED"]),
                    assert_file_column_values("Kind", ["Error", "Warning", "Warning"]),
                    assert_file_column_values("State", ["Current", "Historic", "Historic"]),
                    assert_file_column_values("Date", ["2026-01-01", "2026-01-10", "2025-11-01"]),
                    assert_file_column_values("Date Raised", ["2026-01-15", "2026-01-10", "2026-01-14"]),
                ],
            },
        )

    # An account type or status outside the vocabulary is a source error
    def test_bank_local_corrupt_23(self):
        self._bank_run(
            "corrupt_23",
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 2},
            file_asserts={
                "__bank_balances_current.csv": [assert_file_column_values("Account Type", ["Asset"])],
                "__bank_logs.csv": [assert_file_column_values("Code", ["ACCOUNT_STATUS", "ACCOUNT_TYPE"], sort_by=["Code"])],
            },
        )

    # A balance not fresh is a standing source error, the reading still stored
    def test_bank_local_corrupt_24(self):
        self._bank_run(
            "corrupt_24",
            source=True,
            rerun=False,
            file_asserts={
                "redbark_balances_2026.csv": [assert_file_size(min_rows=2, max_rows=2)],
                "__bank_logs.csv": [assert_file_column_values("Code", ["BALANCE_STALE"])],
            },
        )

    # A dead Redbark id with no replacement is a standing source error
    def test_bank_local_corrupt_25(self):
        self._bank_run(
            "corrupt_25",
            source=True,
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "redbark_transactions_2026.csv": [assert_file_does_not_exist()],
                "__bank_logs.csv": [assert_file_column_values("Code", ["REDBARK_GONE"])],
            },
        )

    # Invalid manual balances hold their file, suspect ones are kept
    def test_bank_local_corrupt_26(self):
        self._bank_run(
            "corrupt_26",
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 3},
            file_asserts={
                "manual_balances_2026.csv": [assert_file_column_values("Balance Manual", ["-50.0", "100.0", "20.0", "5000.0"], sort_by=["Date", "Account"])],
                "manual_balances_2025.csv": [assert_file_columns(["Date", "Time", "Account", "Balance Manual"])],
                "__bank_logs.csv": [assert_file_column_values("Code", ["BALANCE_DUPLICATE", "BALANCE_DUPLICATE", "BALANCE_JUMP", "BALANCE_SIGN", "DATE_BEFORE_FROM"], sort_by=["Code"])],
            },
        )

    # Invalid manual transactions hold their file and year, suspect ones are kept
    def test_bank_local_corrupt_27(self):
        self._bank_run(
            "corrupt_27",
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 11, plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "manual_transactions_2026.csv": [assert_file_size(min_rows=9, max_rows=9), assert_file_columns(["Date", "Account", "Amount", "Description"])],
                "manual_transactions_2025.csv": [assert_file_column_values("Description", ["Lunch", "Lunch", "Treat"], sort_by=["Date", "Description"])],
                "__bank_logs.csv": [
                    assert_file_column_values(
                        "Code",
                        [
                            "ACCOUNT_NOT_MANUAL",
                            "CATEGORY_UNKNOWN",
                            "CLASSIFIER_UNBUCKETED",
                            "DATE_BEFORE_FROM",
                            "DATE_FUTURE",
                            "MANUAL_DUPLICATE",
                            "TRANSACTIONS_UNCLASSIFIED",
                            "TRANSACTIONS_UNVETTED",
                            "TRANSACTION_DECIMALS",
                            "TRANSACTION_DESCRIPTION",
                            "TRANSACTION_ZERO",
                            "VALUE_UNPARSED",
                            "VALUE_UNPARSED",
                            "VALUE_UNPARSED",
                        ],
                        sort_by=["Code"],
                    )
                ],
            },
        )

    # A held transaction Redbark no longer lists inside the window is kept as suspect
    def test_bank_local_corrupt_28(self):
        self._bank_run(
            "corrupt_28",
            standing=1,
            source=True,
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 1},
            file_asserts={
                "redbark_transactions_2026.csv": [assert_file_column_values("Source ID", ["t2", "t1"], sort_by=["Date"])],
                "redbark_transactions_2025.csv": [assert_file_column_values("Source ID", ["t4"])],
                "__bank_logs.csv": [
                    assert_file_column_values(
                        "Code",
                        ["TRANSACTIONS_UNCLASSIFIED", "TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED", "TRANSACTIONS_UNVETTED_CURRENT", "TRANSACTION_GONE"],
                        sort_by=["Code"],
                    )
                ],
            },
        )

    # Classifier errors, one source error per code, hold the edit
    def test_bank_local_corrupt_29(self):
        self._bank_run(
            "corrupt_29",
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 8},
            file_asserts={
                "__bank_logs.csv": [
                    assert_file_column_values(
                        "Code",
                        [
                            "CLASSIFIER_BUCKET",
                            "CLASSIFIER_CATEGORY",
                            "CLASSIFIER_CATEGORY_CASE",
                            "CLASSIFIER_CODE_LIST",
                            "CLASSIFIER_HELD",
                            "CLASSIFIER_PATTERN",
                            "CLASSIFIER_PATTERN_CONFLICT",
                            "CLASSIFIER_SHARE",
                            "CLASSIFIER_UNBUCKETED",
                            "TRANSACTIONS_UNCLASSIFIED_CURRENT",
                            "TRANSACTIONS_UNVETTED_CURRENT",
                        ],
                        sort_by=["Code"],
                    )
                ],
            },
        )

    # A classifier tab with a misplaced column is unusable, nothing classified
    def test_bank_local_corrupt_30(self):
        self._bank_run(
            "corrupt_30",
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "redbark_transactions_2026.csv": [assert_file_column_values("Category Auto", [None])],
                "__bank_logs.csv": [assert_file_column_values("Code", ["TAB_UNUSABLE", "TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED_CURRENT"], sort_by=["Code"])],
            },
        )

    # A category manual typed on the tab survives the Redbark rewrite of its year file
    def test_bank_local_partial_30(self):
        self._bank_run(
            "partial_30",
            source=True,
            sheet_downloads=1,
            file_asserts={
                "redbark_transactions_2026.csv": [
                    assert_file_column_values("Source ID", ["t1", "t2"], sort_by=["Date"]),
                    assert_file_column_values("Category Manual", ["Restaurants", None], sort_by=["Date"]),
                ],
                "__bank_transactions_current.csv": [assert_file_column_values("Bucket", ["Discretionary", None], sort_by=["Date"])],
            },
        )

    # A tab sorted by hand is no edit
    def test_bank_local_partial_31(self):
        self._bank_run(
            "partial_31",
            sheet_downloads=1,
            file_asserts={
                "manual_transactions_2026.csv": [assert_file_size(min_rows=2, max_rows=2)],
                "_sheet_bank_transactions_2026.csv": [assert_file_column_values("Description", ["Coffee", "Fuel", "Lunch"])],
            },
        )

    # An accounts tab edited after the read is not written
    def test_bank_local_partial_32(self):
        self._bank_run(
            "partial_32",
            source=True,
            sheet_downloads=0,
            rerun=False,
            file_asserts={
                "_sheet_bank_accounts.csv": [assert_file_column_values("Status", ["Linked", None])],
                "redbark_balances_2026.csv": [assert_file_size(min_rows=2, max_rows=2)],
            },
        )

    # No accounts tab, every Redbark account checked under its own name
    def test_bank_local_partial_33(self):
        self._bank_run(
            "partial_33",
            source=True,
            file_asserts={
                "__bank_balances_current.csv": [assert_file_column_values("Account", ["Raw One", "Raw Two"], sort_by=["Balance"])],
                "redbark_transactions_2026.csv": [assert_file_column_values("Source ID", ["t1"])],
            },
        )

    # Unsplitting restores one whole transaction
    def test_bank_local_partial_34(self):
        self._bank_run(
            "partial_34",
            sheet_downloads=1,
            file_asserts={
                "redbark_transactions_2026.csv": [assert_file_size(min_rows=1, max_rows=1), assert_file_column_values("Amount Split", ["-1000.0"])],
                "__bank_transactions_current.csv": [assert_file_column_values("Split", ["0"])],
            },
        )

    # Edits on a tab against its base are taken and logged, the tab not re-uploaded
    def test_bank_local_partial_58(self):
        self._bank_run(
            "partial_58",
            file_asserts={
                "redbark_transactions_2026.csv": [
                    assert_file_column_values("Category Manual", ["Food", None, None, None, None, None], sort_by=["Date"]),
                    assert_file_column_values("Vetted", ["Yes", "No", None, None, None, None], sort_by=["Date"]),
                ],
                "_sheet_bank_transactions_2026_v1_1_run.csv": [assert_file_does_not_exist()],
                "__bank_tab_transactions_2026.csv": [assert_file_column_values("Category Manual", [None, None, None, None, None, "Food"])],
                "bank_reclassified_2026_01.csv": [
                    assert_file_column_values("Source", ["sheet", "sheet"]),
                    assert_file_column_values("Description", ["Fuel", "Shop"], sort_by=["Description"]),
                    assert_file_column_values("Manual After", [None, "Food"], sort_by=["Description"]),
                    assert_file_column_values("Vetted After", ["No", "Yes"], sort_by=["Description"]),
                    assert_file_nones_per_col(include=r"File MD5"),
                ],
            },
        )

    # A tab edit wins its cell over a Drive edit and follows a re-dated row by source id
    def test_bank_local_partial_59(self):
        self._bank_run(
            "partial_59",
            file_asserts={
                "redbark_transactions_2026.csv": [
                    assert_file_column_values("Category Manual", ["Food", None], sort_by=["Date"]),
                    assert_file_column_values("Vetted", ["No", "Yes"], sort_by=["Date"]),
                ],
            },
        )

    # An edit on a row no file holds is unmatched, a short or resorted tab no edit
    def test_bank_local_corrupt_36(self):
        self._bank_run(
            "corrupt_36",
            errored={plugin.CTR_SRC_DATA: 1},
            rerun=False,
            file_asserts={
                "redbark_transactions_2026.csv": [
                    assert_file_size(min_rows=4, max_rows=4),
                    assert_file_column_values("Amount Split", ["-10.0", "-15.0", "-15.0", "-5.0"], sort_by=["Date", "Amount Split"]),
                    assert_file_column_values("Category Manual", [None, "Car", "Food", None], sort_by=["Date", "Category Manual"]),
                ],
                "__bank_logs.csv": [assert_file_column_values("Code", ["EDIT_UNMATCHED", "TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED_CURRENT"], sort_by=["Code"])],
                "bank_reclassified_2026_01.csv": [
                    assert_file_column_values("Part", ["1", "2"], sort_by=["Part"]),
                    assert_file_column_values("Split Before", ["-10.0", "-20.0"], sort_by=["Part"]),
                    assert_file_column_values("Split After", ["-15.0", "-15.0"], sort_by=["Part"]),
                    assert_file_column_values("Manual Before", ["Food", "Car"], sort_by=["Part"]),
                ],
            },
        )

    # A year file changed on Drive mid-run conflicts and holds its tab, base, log and record back
    def test_bank_local_corrupt_37(self):
        self._bank_run(
            "corrupt_37",
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "redbark_transactions_2026.csv": [assert_file_column_values("Vetted", ["Yes", None], sort_by=["Date"])],
                "_sheet_bank_transactions_2026_v1.csv": [assert_file_does_not_exist()],
                "__bank_tab_transactions_2026.csv": [assert_file_column_values("Vetted", [None, None])],
                "__bank_committed.json": [assert_file_does_not_exist()],
                "__bank_logs.csv": [assert_file_column_values("Code", ["DRIVE_CONFLICT", "TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED_CURRENT"], sort_by=["Code"])],
                "bank_reclassified_2026_01.csv": [assert_file_does_not_exist()],
            },
        )

    # A run killed mid-way and run again ends as an uninterrupted run does
    def test_bank_local_partial_60(self):
        def _bank(_kill=None):
            reset_config(log="warning")
            plugin.config.repo_scope = plugin.RepoScope.LOCAL
            plugin.config.disable_source_downloads = True
            plugin.config.disable_sheet_downloads = True
            plugin.config.disable_database_downloads = True
            plugin.config.clock = datetime.datetime.fromisoformat("2026-01-15T12:00:00")
            bank = importlib.import_module("wrangle.plugin.bank").Bank()
            self._load_caches(bank, join(DIR_ROOT, "src/test/resources/repos/local/bank/partial_60/data"))
            if _kill is not None:
                calls = {"count": 0}
                original = getattr(Plugin, _kill)

                def _killed(_self, *_args, **_kwargs):
                    calls["count"] += 1
                    if calls["count"] == 1:
                        raise _Killed()
                    return original(_self, *_args, **_kwargs)

                with mock.patch.object(Plugin, _kill, _killed), self.assertRaises(_Killed):
                    bank.run()
            bank.run()
            return {
                name: open(join(bank.local_cache, name), "rb").read()
                for name in ("redbark_transactions_2026.csv", "__bank_tab_transactions_2026.csv", "__bank_committed.json", "__bank_transactions_current.csv")
            }

        expected = _bank()
        for kill in ("csv_write", "state_cache", "sheet_upload", "logs_merged"):
            self.assertEqual(expected, _bank(kill), kill)

    # An idle run makes one Drive listing and one sheet read and uploads nothing
    def test_bank_local_partial_61(self):
        drive = bank_drive_offline("partial_61")
        assert drive is not None
        reads = []

        def _values(_self, _key, _titles):
            reads.append(list(_titles))
            cells = {}
            for title in _titles:
                path = _self._sheet_cache_path(f"bank_{title}".lower())
                if path is not None:
                    with open(path) as tab_file:
                        cells[title] = list(csv.reader(tab_file))
            return cells

        mock.patch.object(Plugin, "_sheet_values", _values).start()
        mock.patch.object(plugin.Repos, "__getattr__", lambda _self, name: {"drive_folder": "folder", "sheet_key": "key"}.get(name)).start()
        reset_config(log="warning")
        plugin.config.repo_scope = plugin.RepoScope.LOCAL
        plugin.config.disable_source_downloads = True
        plugin.config.disable_database_downloads = True
        plugin.config.disable_drive_downloads = False
        plugin.config.disable_drive_uploads = False
        plugin.config.clock = datetime.datetime.fromisoformat("2026-01-15T12:00:00")
        bank = importlib.import_module("wrangle.plugin.bank").Bank()
        self._load_caches(bank, join(DIR_ROOT, "src/test/resources/repos/local/bank/partial_61/data"))
        bank.run()
        drive.calls.clear()
        reads.clear()
        bank.reset_counters()
        bank.run()
        self.assertEqual(({"list": 1}, 1), (dict(drive.calls), len(reads)))
        self.assertEqual(0, bank.get_counter(plugin.CTR_SRC_EGRESS, plugin.CTR_ACT_SHEET_ROWS))

    # The weekly sweep checks ninety days, raising gone, relisted and unheld transactions
    def test_bank_local_corrupt_38(self):
        self._bank_run(
            "corrupt_38",
            today="2026-03-01T12:00:00",
            source=True,
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 2},
            file_asserts={
                "redbark_transactions_2026.csv": [
                    assert_file_size(min_rows=5, max_rows=5),
                    assert_file_column_values("Source ID", [None, "s3", "s1", "s2n", "s7"], sort_by=["Date"]),
                    assert_file_column_values("Date Posted", [None, "2026-01-11", "2026-01-21", "2026-01-22", "2026-02-26"], sort_by=["Date"]),
                ],
                "__bank_logs.csv": [
                    assert_file_column_values(
                        "Code",
                        [
                            "TRANSACTIONS_UNCLASSIFIED",
                            "TRANSACTIONS_UNVETTED",
                            "TRANSACTION_GONE",
                            "TRANSACTION_RELISTED",
                            "TRANSACTION_RELISTED",
                            "TRANSACTION_RELISTED",
                            "TRANSACTION_UNHELD",
                        ],
                        sort_by=["Code"],
                    )
                ],
            },
        )

    # A new AMEX export maps by overlap, is renamed and imported
    def test_bank_local_partial_62(self):
        self._bank_run(
            "partial_62",
            file_asserts={
                "activity.csv": [assert_file_does_not_exist()],
                "amex_xxxx0002_transactions_2026-01-14.csv": [assert_file_size(min_rows=7, max_rows=7)],
                "manual_transactions_2026.csv": [
                    assert_file_size(min_rows=7, max_rows=7),
                    assert_file_columns(list(TRANSACTIONS_SCHEMA)),
                    assert_file_column_values(
                        "Description", ["REFUND THREE", "SPLIT FOUR", "SPLIT FOUR", "SHOP TWO", "SHOP TWO", "SHOP TWO", "CAFE  ONE    PERTH"], sort_by=["Date", "Category Manual"]
                    ),
                    assert_file_column_values("Amount", ["20.0", "-30.0", "-30.0", "-12.0", "-12.0", "-12.0", "-4.5"], sort_by=["Date", "Category Manual"]),
                    assert_file_column_values("Amount Split", ["20.0", "-20.0", "-10.0", "-12.0", "-12.0", "-12.0", "-4.5"], sort_by=["Date", "Amount Split", "Category Manual"]),
                    assert_file_column_values("Category Manual", [None, None, None, None, None, "Groceries", None], sort_by=["Date", "Category Manual"]),
                    assert_file_column_values("Date Posted", ["2026-01-03", "2026-01-11", "2026-01-11", "2026-01-14", "2026-01-14", "2026-01-14", "2026-01-15"], sort_by=["Date"]),
                    assert_file_column_distinct("Transaction ID", 6),
                ],
                "__bank_transactions_current.csv": [assert_file_size(min_rows=7, max_rows=7), assert_file_column_distinct("Transaction ID", 6)],
            },
        )

    # Overlapping and identical AMEX exports map by card and add each row once
    def test_bank_local_partial_63(self):
        self._bank_run(
            "partial_63",
            file_asserts={
                "amex_xxxx0002_transactions_2026-01-12.csv": [assert_file_size(min_rows=3, max_rows=3)],
                "amex_xxxx0002_transactions_2026-01-12_2.csv": [assert_file_size(min_rows=3, max_rows=3)],
                "activity.csv": [assert_file_does_not_exist()],
                "activity-2.csv": [assert_file_does_not_exist()],
                "manual_transactions_2026.csv": [assert_file_column_values("Description", ["COFFEE", "LUNCH", "DINNER"], sort_by=["Date"])],
            },
        )

    # A standard run reads only exports changed on Drive
    def test_bank_local_partial_64(self):
        self._bank_run(
            "partial_64",
            file_asserts={"manual_transactions_2026.csv": [assert_file_column_values("Description", ["COFFEE", "DINNER"], sort_by=["Date"])]},
        )

    # A forced download reads every export again
    def test_bank_local_partial_65(self):
        self._bank_run(
            "partial_65",
            rerun=False,
            downloads=True,
            file_asserts={"manual_transactions_2026.csv": [assert_file_column_values("Description", ["COFFEE", "LUNCH", "DINNER"], sort_by=["Date"])]},
        )

    # AMEX exports renamed by hand, of a linked account or unmapped
    def test_bank_local_corrupt_39(self):
        self._bank_run(
            "corrupt_39",
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 1, plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "activity.csv": [assert_file_does_exist()],
                "manual_transactions_2026.csv": [assert_file_column_values("Description", ["BOOKS"]), assert_file_column_values("Account", ["Other Card"])],
                "__bank_logs.csv": [assert_file_column_values("Code", ["ACCOUNT_LINKED", "IMPORT_UNMAPPED", "TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED_CURRENT"], sort_by=["Code"])],
            },
        )

    # An unreadable AMEX export is left unrenamed and unimported
    def test_bank_local_corrupt_40(self):
        self._bank_run(
            "corrupt_40",
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 3},
            file_asserts={
                "activity.csv": [assert_file_does_exist()],
                "activity-2.csv": [assert_file_does_exist()],
                "activity-3.csv": [assert_file_does_exist()],
                "manual_transactions_2026.csv": [assert_file_does_not_exist()],
                "__bank_logs.csv": [assert_file_column_values("Code", ["IMPORT_UNREADABLE"] * 3)],
            },
        )

    # Held rows inside an export's dates that no export lists are gone or suspect
    def test_bank_local_corrupt_41(self):
        self._bank_run(
            "corrupt_41",
            file_asserts={
                "manual_transactions_2026.csv": [assert_file_size(min_rows=5, max_rows=5)],
                "__bank_logs.csv": [
                    assert_file_column_values(
                        "Code",
                        ["IMPORT_GONE", "IMPORT_GONE", "IMPORT_SUSPECT", "TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED_CURRENT"],
                        sort_by=["Code"],
                    )
                ],
            },
        )

    # An AMEX export whose Drive rename fails keeps its name and is not imported
    def test_bank_local_corrupt_42(self):
        def _drive_rename(self, *_args, **_kwargs):
            self.add_counter(plugin.CTR_SRC_EGRESS, plugin.CTR_ACT_ERRORED)
            return False

        mock.patch.object(Plugin, "drive_rename", _drive_rename).start()
        self._bank_run(
            "corrupt_42",
            rerun=False,
            errored={plugin.CTR_SRC_EGRESS: 1},
            file_asserts={
                "activity.csv": [assert_file_does_exist()],
                "manual_transactions_2026.csv": [assert_file_column_values("Description", ["COFFEE", "LUNCH"], sort_by=["Date"])],
            },
        )

    # Lots of current data, a specific amount of new data, no remote source data downloads, downloads and uploads from and to preview data repo
    def test_bank_preview_replete_1(self):
        fixture = _load_fixture("preview", "bank", "replete_1")
        drive_delete(REPOS_BANK._scopes["preview"]["drive_folder"], "redbark_balances_2019.csv")
        self.run_plugin(
            "bank",
            plugin.RepoScope.PREVIEW,
            "replete_1",
            log_level="info",
            disable_sheet_downloads=True,
            disable_database_downloads=True,
            disable_drive_downloads=False,
            disable_source_downloads=True,
            disable_sheet_uploads=False,
            disable_database_uploads=True,
            disable_drive_uploads=False,
            enable_rerun=True,
            force_reprocessing=False,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_SOURCES: {
                            plugin.CTR_ACT_UPLOADED: 1,
                        },
                        plugin.CTR_SRC_FILES: {
                            plugin.CTR_ACT_PROCESSED: fixture["files_processed"],
                        },
                        plugin.CTR_SRC_DATA: {
                            plugin.CTR_ACT_CURRENT_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_UPDATE_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_DELTA_COLUMNS: fixture["cols_data"],
                        },
                    },
                },
            ),
            custom_asserts=[
                assert_custom_rows_delta(equals=fixture["rows_delta"], state="bank_balances"),
                assert_custom_rows_delta(equals=fixture["transactions_rows_delta"], state="bank_transactions"),
            ],
            file_asserts={
                "redbark_balances_2019.csv": [assert_file_size()],
                "__bank_balances_current.csv": [
                    assert_file_size(),
                    assert_file_dates(end_date=fixture["end_date"], descending=False),
                    assert_file_nones_per_row(exclude=r"Balance Manual|Balance Auto|Account Institution|Account Number|Account Type"),
                ],
                "__bank_transactions_current.csv": [
                    assert_file_size(min_rows=fixture["transactions_rows"], max_rows=fixture["transactions_rows"]),
                    assert_file_dates(end_date=fixture["transactions_end_date"], descending=False),
                    assert_file_column_distinct("Transaction ID", fixture["transactions_ids"]),
                ],
                "_sheet_bank_balances.csv": [assert_file_size(), assert_file_columns(list(BALANCES_SCHEMA))],
                "_sheet_bank_logs.csv": [assert_file_columns(list(LOG_SCHEMA))],
            },
        )

    # Lots of current data, a lot of live new data, downloads from remote sources, downloads from release data repo, no remote data repo uploads
    def test_bank_release_replete_1(self):
        fixture = _load_fixture("release", "bank", "replete_1")
        self.run_plugin(
            "bank",
            plugin.RepoScope.RELEASE,
            "replete_1",
            today=(datetime.datetime.now().astimezone() + datetime.timedelta(hours=BALANCES_MAX_AGE_HOURS + 1)).strftime("%Y-%m-%dT%H:%M:%S"),
            log_level="info",
            disable_sheet_downloads=False,
            disable_database_downloads=False,
            disable_drive_downloads=False,
            disable_source_downloads=False,
            disable_sheet_uploads=True,
            disable_database_uploads=True,
            disable_drive_uploads=True,
            enable_rerun=False,
            force_reprocessing=False,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_DATA: {
                            plugin.CTR_ACT_CURRENT_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_UPDATE_COLUMNS: fixture["cols_data"],
                        },
                    },
                    "counter_at_least": {
                        plugin.CTR_SRC_SOURCES: {
                            plugin.CTR_ACT_DOWNLOADED: 2,
                        },
                        plugin.CTR_SRC_DATA: {
                            plugin.CTR_ACT_DELTA_ROWS: fixture["rows_delta"],
                        },
                    },
                },
            ),
            file_asserts={
                "_redbark_balances.csv": [assert_file_size()],
                "_redbark_transactions.csv": [assert_file_size()],
                "__bank_balances_current.csv": [
                    assert_file_size(),
                    assert_file_dates(end_date_at_least=fixture["end_date"] or None, descending=False),
                ],
                "__bank_transactions_current.csv": [
                    assert_file_size(),
                    assert_file_dates(end_date_at_least=fixture["transactions_end_date"] or None, descending=False),
                ],
            },
        )

    ########################################################################################################################
    # Currency
    ########################################################################################################################

    # No current data, no new data, no remote source data downloads, no remote data repo downloads or uploads
    def test_currency_local_blank_1(self):
        fixture = _load_fixture("local", "currency", "blank_1")
        self.run_plugin(
            "currency",
            plugin.RepoScope.LOCAL,
            "blank_1",
            log_level="info",
            disable_sheet_downloads=True,
            disable_database_downloads=True,
            disable_drive_downloads=True,
            disable_source_downloads=True,
            disable_sheet_uploads=True,
            disable_database_uploads=True,
            disable_drive_uploads=True,
            enable_rerun=False,
            force_reprocessing=False,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_FILES: {
                            plugin.CTR_ACT_ERRORED: fixture["expected_errors"],
                        },
                    },
                },
            ),
            file_asserts={
                "__currency_current.csv": [
                    assert_file_does_not_exist(),
                ],
            },
        )

    # No current data, corrupt data, no remote source data downloads, no remote data repo downloads or uploads
    def test_currency_local_corrupt_1(self):
        fixture = _load_fixture("local", "currency", "corrupt_1")
        self.run_plugin(
            "currency",
            plugin.RepoScope.LOCAL,
            "corrupt_1",
            log_level="fatal",
            disable_sheet_downloads=True,
            disable_database_downloads=True,
            disable_drive_downloads=True,
            disable_source_downloads=True,
            disable_sheet_uploads=True,
            disable_database_uploads=True,
            disable_drive_uploads=True,
            enable_rerun=False,
            force_reprocessing=True,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_FILES: {
                            plugin.CTR_ACT_ERRORED: fixture["expected_errors"],
                        },
                    },
                },
            ),
            file_asserts={
                "__currency_current.csv": [
                    assert_file_does_not_exist(),
                ],
            },
        )

    # No current data, corrupt data, no remote source data downloads, no remote data repo downloads or uploads
    def test_currency_local_corrupt_2(self):
        fixture = _load_fixture("local", "currency", "corrupt_2")
        self.run_plugin(
            "currency",
            plugin.RepoScope.LOCAL,
            "corrupt_2",
            log_level="fatal",
            disable_sheet_downloads=True,
            disable_database_downloads=True,
            disable_drive_downloads=True,
            disable_source_downloads=True,
            disable_sheet_uploads=True,
            disable_database_uploads=True,
            disable_drive_uploads=True,
            enable_rerun=False,
            force_reprocessing=True,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_FILES: {
                            plugin.CTR_ACT_ERRORED: fixture["expected_errors"],
                        },
                    },
                },
            ),
            file_asserts={
                "__currency_current.csv": [
                    assert_file_does_not_exist(),
                ],
            },
        )

    # Lots of current data, a specific amount of new data, no remote source data downloads, downloads and uploads from and to preview data repo
    def test_currency_preview_replete_1(self):
        fixture = _load_fixture("preview", "currency", "replete_1")
        drive_delete(REPOS_CURRENCY._scopes["preview"]["drive_folder"], "rba_fx_1987-1990.xls")
        drive_delete(REPOS_CURRENCY._scopes["preview"]["drive_folder"], "rba_fx_2023-current.xls")
        self.run_plugin(
            "currency",
            plugin.RepoScope.PREVIEW,
            "replete_1",
            log_level="info",
            disable_sheet_downloads=True,
            disable_database_downloads=True,
            disable_drive_downloads=False,
            disable_source_downloads=True,
            disable_sheet_uploads=False,
            disable_database_uploads=True,
            disable_drive_uploads=False,
            enable_rerun=True,
            force_reprocessing=False,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_SOURCES: {
                            plugin.CTR_ACT_UPLOADED: 2,
                        },
                        plugin.CTR_SRC_DATA: {
                            plugin.CTR_ACT_PREVIOUS_COLUMNS: len(CURRENCY_COLUMNS),
                            plugin.CTR_ACT_CURRENT_COLUMNS: len(CURRENCY_COLUMNS),
                            plugin.CTR_ACT_UPDATE_COLUMNS: 0,
                            plugin.CTR_ACT_DELTA_COLUMNS: 0,
                            plugin.CTR_ACT_DELTA_ROWS: 0,
                        },
                    },
                },
            ),
            custom_asserts=[assert_custom_rows_delta(equals=fixture["rows_delta"])],
            file_asserts={
                "__currency_current.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="1983-12-12", end_date=fixture["end_date"], contiguous="days"),
                    assert_file_nones_per_row(),
                    assert_file_zeroes_per_col(exclude=r"Delta"),
                ],
                "_sheet_rates_currency.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="2006-01-02", end_date=fixture["end_date"], contiguous="days", descending=True),
                    assert_file_nones_per_row(),
                    assert_file_zeroes_per_row(),
                ],
                "_database_currency.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="1983-12-12", end_date=fixture["end_date"], contiguous="days"),
                    assert_file_nones_per_row(),
                ],
            },
        )

    # Lots of current data, a lot of live new data, downloads from remote sources, downloads from release data repo, no remote data repo uploads
    def test_currency_release_replete_1(self):
        fixture = _load_fixture("release", "currency", "replete_1")
        self.run_plugin(
            "currency",
            plugin.RepoScope.RELEASE,
            "replete_1",
            log_level="info",
            disable_sheet_downloads=False,
            disable_database_downloads=False,
            disable_drive_downloads=False,
            disable_source_downloads=False,
            disable_sheet_uploads=True,
            disable_database_uploads=True,
            disable_drive_uploads=True,
            enable_rerun=True,
            force_reprocessing=False,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_DATA: {
                            plugin.CTR_ACT_PREVIOUS_COLUMNS: len(CURRENCY_COLUMNS),
                            plugin.CTR_ACT_CURRENT_COLUMNS: len(CURRENCY_COLUMNS),
                            plugin.CTR_ACT_UPDATE_COLUMNS: len(CURRENCY_COLUMNS),
                            plugin.CTR_ACT_DELTA_COLUMNS: len(CURRENCY_COLUMNS),
                        },
                    },
                    "counter_at_least": {
                        plugin.CTR_SRC_DATA: {
                            plugin.CTR_ACT_DELTA_ROWS: fixture["rows_delta"],
                        },
                    },
                },
            ),
            custom_asserts=[assert_custom_rows_delta(at_least=fixture["rows_delta"])],
            file_asserts={
                "__currency_current*.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="1983-12-12", end_date_at_least=fixture["end_date"], contiguous="days"),
                    assert_file_nones_per_row(),
                    assert_file_zeroes_per_col(exclude=r"Delta"),
                    assert_file_equal(),
                ],
                "_sheet_rates_currency*.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="2006-01-02", end_date_at_least=fixture["end_date"], contiguous="days", descending=True),
                    assert_file_nones_per_row(),
                    assert_file_zeroes_per_row(),
                    assert_file_equal(),
                ],
                "_database_currency*.csv": [
                    assert_file_size(),
                    assert_file_nones_per_row(),
                    assert_file_subset(),
                ],
            },
        )

    ########################################################################################################################
    # Equity
    ########################################################################################################################

    # No current data, no new data, no remote source data downloads, no remote data repo downloads or uploads
    def test_equity_local_blank_1(self):
        fixture = _load_fixture("local", "equity", "blank_1")
        self.run_plugin(
            "equity",
            plugin.RepoScope.LOCAL,
            "blank_1",
            log_level="info",
            disable_sheet_downloads=True,
            disable_database_downloads=True,
            disable_drive_downloads=True,
            disable_source_downloads=True,
            disable_sheet_uploads=True,
            disable_database_uploads=True,
            disable_drive_uploads=True,
            enable_rerun=False,
            force_reprocessing=False,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_FILES: {
                            plugin.CTR_ACT_ERRORED: fixture["expected_errors"],
                        },
                    },
                },
            ),
            file_asserts={
                "__equity_current.csv": [
                    assert_file_does_not_exist(),
                ],
            },
        )

    # No current data, corrupt data, no remote source data downloads, no remote data repo downloads or uploads
    def test_equity_local_corrupt_1(self):
        fixture = _load_fixture("local", "equity", "corrupt_1")
        self.run_plugin(
            "equity",
            plugin.RepoScope.LOCAL,
            "corrupt_1",
            log_level="fatal",
            disable_sheet_downloads=True,
            disable_database_downloads=True,
            disable_drive_downloads=True,
            disable_source_downloads=True,
            disable_sheet_uploads=True,
            disable_database_uploads=True,
            disable_drive_uploads=True,
            enable_rerun=False,
            force_reprocessing=True,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_FILES: {
                            plugin.CTR_ACT_ERRORED: fixture["expected_errors"],
                        },
                    },
                },
            ),
            file_asserts={
                "__equity_current.csv": [
                    assert_file_does_not_exist(),
                ],
            },
        )

    # No current data, corrupt data, no remote source data downloads, no remote data repo downloads or uploads
    def test_equity_local_corrupt_2(self):
        fixture = _load_fixture("local", "equity", "corrupt_2")
        self.run_plugin(
            "equity",
            plugin.RepoScope.LOCAL,
            "corrupt_2",
            log_level="debug",
            disable_sheet_downloads=True,
            disable_database_downloads=True,
            disable_drive_downloads=True,
            disable_source_downloads=True,
            disable_sheet_uploads=True,
            disable_database_uploads=True,
            disable_drive_uploads=True,
            enable_rerun=False,
            force_reprocessing=True,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_FILES: {
                            plugin.CTR_ACT_ERRORED: fixture["expected_errors"],
                        },
                    },
                },
            ),
            file_asserts={
                "__equity_current.csv": [
                    assert_file_does_not_exist(),
                ],
            },
        )

    # No current data, month files whose successor repeats their last bar, no remote source data downloads, no remote data repo downloads or uploads
    def test_equity_local_corrupt_3(self):
        fixture = _load_fixture("local", "equity", "corrupt_3")
        self.run_plugin(
            "equity",
            plugin.RepoScope.LOCAL,
            "corrupt_3",
            log_level="fatal",
            disable_sheet_downloads=True,
            disable_database_downloads=True,
            disable_drive_downloads=True,
            disable_source_downloads=True,
            disable_sheet_uploads=True,
            disable_database_uploads=True,
            disable_drive_uploads=True,
            enable_rerun=False,
            force_reprocessing=True,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_FILES: {
                            plugin.CTR_ACT_PROCESSED: fixture["files_processed"],
                            plugin.CTR_ACT_ERRORED: fixture["expected_errors"],
                        },
                        plugin.CTR_SRC_DATA: {
                            plugin.CTR_ACT_CURRENT_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_DELTA_ROWS: fixture["rows_delta"],
                        },
                    },
                },
            ),
            file_asserts={
                "__equity_current.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="2025-09-01", end_date=fixture["end_date"], contiguous="days"),
                ],
            },
        )

    # Lots of current data, a specific amount of new data, no remote source data downloads, no remote data repo downloads or uploads
    def test_equity_local_partial_1(self):
        fixture = _load_fixture("local", "equity", "partial_1")
        self.run_plugin(
            "equity",
            plugin.RepoScope.LOCAL,
            "partial_1",
            log_level="info",
            disable_sheet_downloads=True,
            disable_database_downloads=True,
            disable_drive_downloads=True,
            disable_source_downloads=True,
            disable_sheet_uploads=True,
            disable_database_uploads=True,
            disable_drive_uploads=True,
            enable_rerun=False,
            force_reprocessing=True,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_FILES: {
                            plugin.CTR_ACT_PROCESSED: fixture["files_processed"],
                        },
                    },
                },
            ),
        )

    # Lots of current data, a specific amount of new data, no remote source data downloads, no remote data repo downloads or uploads
    def test_equity_local_partial_2(self):
        fixture = _load_fixture("local", "equity", "partial_2")
        self.run_plugin(
            "equity",
            plugin.RepoScope.LOCAL,
            "partial_2",
            log_level="info",
            disable_sheet_downloads=True,
            disable_database_downloads=True,
            disable_drive_downloads=True,
            disable_source_downloads=True,
            disable_sheet_uploads=True,
            disable_database_uploads=True,
            disable_drive_uploads=True,
            enable_rerun=False,
            force_reprocessing=True,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_FILES: {
                            plugin.CTR_ACT_PROCESSED: fixture["files_processed"],
                        },
                        plugin.CTR_SRC_DATA: {
                            plugin.CTR_ACT_PREVIOUS_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_CURRENT_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_UPDATE_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_DELTA_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_DELTA_ROWS: fixture["rows_delta"],
                        },
                    },
                },
            ),
            file_asserts={
                "__equity_current.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="2025-01-02", end_date=fixture["end_date"], contiguous="days"),
                    assert_file_nones_per_col(after_first_rows=True),
                    assert_file_zeroes_per_row(exclude=r"Market Volume|Change"),
                ],
                "_sheet_prices_history.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="2025-01-02", end_date=fixture["end_date"], contiguous="days", descending=True),
                    assert_file_nones_per_col(after_last_rows=True),
                    assert_file_zeroes_per_row(),
                ],
                "_database_equity.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="2025-01-02", end_date=fixture["end_date"], contiguous="days"),
                    assert_file_nones_per_col(after_first_rows=True),
                ],
            },
        )

    # Current data with year-boundary interpolations anchored on since-revised closes, one new source file served offline from
    # local cache, incremental run must reprocess the predecessor file so the corrected boundary rows match a full re-process
    def test_equity_local_partial_3(self):
        fixture = _load_fixture("local", "equity", "partial_3")
        stock_download_offline({"yahoo_acdc_2024.csv"})
        self.run_plugin(
            "equity",
            plugin.RepoScope.LOCAL,
            "partial_3",
            log_level="info",
            disable_sheet_downloads=True,
            disable_database_downloads=True,
            disable_drive_downloads=True,
            disable_source_downloads=False,
            disable_sheet_uploads=True,
            disable_database_uploads=True,
            disable_drive_uploads=True,
            enable_rerun=True,
            force_reprocessing=False,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_SOURCES: {
                            plugin.CTR_ACT_DOWNLOADED: 1,
                        },
                        plugin.CTR_SRC_FILES: {
                            plugin.CTR_ACT_PROCESSED: fixture["files_processed"],
                        },
                        plugin.CTR_SRC_DATA: {
                            plugin.CTR_ACT_PREVIOUS_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_CURRENT_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_UPDATE_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_DELTA_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_DELTA_ROWS: fixture["rows_delta"],
                        },
                    },
                },
            ),
            file_asserts={
                "__equity_current*.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="2023-12-18", end_date=fixture["end_date"], contiguous="days"),
                    assert_file_nones_per_col(after_first_rows=True),
                    assert_file_zeroes_per_row(exclude=r"Market Volume|Change"),
                    assert_file_equal(),
                ],
            },
        )

    # Current data a year stale, two new source files served offline from local cache, incremental run must reprocess the
    # predecessor file behind the earliest new file and chain across the consecutive new files
    def test_equity_local_partial_4(self):
        fixture = _load_fixture("local", "equity", "partial_4")
        stock_download_offline({"yahoo_acdc_2023.csv", "yahoo_acdc_2024.csv"})
        self.run_plugin(
            "equity",
            plugin.RepoScope.LOCAL,
            "partial_4",
            log_level="info",
            disable_sheet_downloads=True,
            disable_database_downloads=True,
            disable_drive_downloads=True,
            disable_source_downloads=False,
            disable_sheet_uploads=True,
            disable_database_uploads=True,
            disable_drive_uploads=True,
            enable_rerun=True,
            force_reprocessing=False,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_SOURCES: {
                            plugin.CTR_ACT_DOWNLOADED: 2,
                        },
                        plugin.CTR_SRC_FILES: {
                            plugin.CTR_ACT_PROCESSED: fixture["files_processed"],
                        },
                        plugin.CTR_SRC_DATA: {
                            plugin.CTR_ACT_PREVIOUS_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_CURRENT_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_UPDATE_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_DELTA_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_DELTA_ROWS: fixture["rows_delta"],
                        },
                    },
                },
            ),
            file_asserts={
                "__equity_current*.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="2022-12-19", end_date=fixture["end_date"], contiguous="days"),
                    assert_file_nones_per_col(after_first_rows=True),
                    assert_file_zeroes_per_row(exclude=r"Market Volume|Change"),
                    assert_file_equal(),
                ],
            },
        )

    # Lots of current data, a specific amount of new data, no remote source data downloads, no remote data repo downloads or uploads
    def test_equity_local_replete_1(self):
        fixture = _load_fixture("local", "equity", "replete_1")
        self.run_plugin(
            "equity",
            plugin.RepoScope.LOCAL,
            "replete_1",
            log_level="info",
            disable_sheet_downloads=True,
            disable_database_downloads=True,
            disable_drive_downloads=True,
            disable_source_downloads=True,
            disable_sheet_uploads=True,
            disable_database_uploads=True,
            disable_drive_uploads=True,
            enable_rerun=False,
            force_reprocessing=True,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_FILES: {
                            plugin.CTR_ACT_PROCESSED: fixture["files_processed"],
                        },
                        plugin.CTR_SRC_DATA: {
                            plugin.CTR_ACT_PREVIOUS_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_CURRENT_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_UPDATE_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_DELTA_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_DELTA_ROWS: fixture["rows_delta"],
                        },
                    },
                },
            ),
            file_asserts={
                "__equity_current.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="1982-04-01", end_date=fixture["end_date"], contiguous="days"),
                    assert_file_nones_per_col(after_first_rows=True),
                    assert_file_zeroes_per_row(exclude=r"Market Volume|Change"),
                ],
                "_sheet_prices_history.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="2007-01-01", end_date=fixture["end_date"], contiguous="days", descending=True),
                    assert_file_nones_per_col(after_last_rows=True),
                    assert_file_zeroes_per_row(),
                ],
                "_database_equity.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="1982-04-01", end_date=fixture["end_date"], contiguous="days"),
                    assert_file_nones_per_col(after_first_rows=True),
                ],
            },
        )

    # An index weights tab that cannot be read skips the commit and the uploads and errors every file, as a failed commit does
    def test_equity_local_corrupt_4(self):
        sheet_download = Plugin.sheet_download

        def _sheet_download(self, drive_key, workbook_name, *args, **kwargs):
            if workbook_name == "Portfolio":
                raise RuntimeError("index weights unreadable")
            return sheet_download(self, drive_key, workbook_name, *args, **kwargs)

        mock.patch.object(Plugin, "sheet_download", _sheet_download).start()
        reset_config(log="warning")
        plugin.config.repo_scope = plugin.RepoScope.LOCAL
        for flag in ("disable_source_downloads", "disable_sheet_downloads", "disable_database_downloads", "disable_drive_downloads"):
            setattr(plugin.config, flag, True)
        plugin.config.force_reprocessing = True
        equity = importlib.import_module("wrangle.plugin.equity").Equity()
        data_dir = join(DIR_ROOT, "src/test/resources/repos/local/equity/replete_1/data")
        self._load_caches(equity, data_dir)
        equity.run()
        self.assertTrue(filecmp.cmp(join(data_dir, "__equity_current.csv"), join(equity.local_cache, "__equity_current.csv"), shallow=False))
        self.assertEqual([], glob.glob(join(equity.local_cache, "_sheet_prices_history*")) + glob.glob(join(equity.local_cache, "_database_equity.csv")))
        processed, errored = (equity.get_counter(plugin.CTR_SRC_FILES, action) for action in (plugin.CTR_ACT_PROCESSED, plugin.CTR_ACT_ERRORED))
        self.assertEqual((True, processed + equity.get_counter(plugin.CTR_SRC_FILES, plugin.CTR_ACT_SKIPPED)), (processed > 0, errored))

    # Lots of current data, a specific amount of new data, no remote source data downloads, downloads and uploads from and to preview data repo
    def test_equity_preview_replete_1(self):
        fixture = _load_fixture("preview", "equity", "replete_1")
        drive_delete(REPOS_EQUITY._scopes["preview"]["drive_folder"], "yahoo_acdc_2018.csv")
        self.run_plugin(
            "equity",
            plugin.RepoScope.PREVIEW,
            "replete_1",
            log_level="info",
            disable_sheet_downloads=True,
            disable_database_downloads=True,
            disable_drive_downloads=False,
            disable_source_downloads=True,
            disable_sheet_uploads=False,
            disable_database_uploads=True,
            disable_drive_uploads=False,
            enable_rerun=True,
            force_reprocessing=False,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_SOURCES: {
                            plugin.CTR_ACT_UPLOADED: 1,
                        },
                        plugin.CTR_SRC_DATA: {
                            plugin.CTR_ACT_PREVIOUS_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_CURRENT_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_UPDATE_COLUMNS: 0,
                            plugin.CTR_ACT_DELTA_COLUMNS: 0,
                            plugin.CTR_ACT_DELTA_ROWS: 0,
                        },
                    },
                },
            ),
            custom_asserts=[assert_custom_rows_delta(equals=fixture["rows_delta"])],
            file_asserts={
                "__equity_current.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="1982-04-01", end_date=fixture["end_date"], contiguous="days"),
                    assert_file_nones_per_col(after_first_rows=True),
                    assert_file_zeroes_per_row(exclude=r"Market Volume|Change"),
                ],
                "_sheet_prices_history.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="2007-01-01", end_date=fixture["end_date"], contiguous="days", descending=True),
                    assert_file_nones_per_col(after_last_rows=True),
                    assert_file_zeroes_per_row(),
                ],
                "_database_equity.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="1982-04-01", end_date=fixture["end_date"], contiguous="days"),
                    assert_file_nones_per_col(after_first_rows=True),
                ],
            },
        )

    # Lots of current data, a lot of live new data, downloads from remote sources, downloads from release data repo, no remote data repo uploads
    def test_equity_release_replete_1(self):
        fixture = _load_fixture("release", "equity", "replete_1")
        self.run_plugin(
            "equity",
            plugin.RepoScope.RELEASE,
            "replete_1",
            log_level="info",
            disable_sheet_downloads=False,
            disable_database_downloads=False,
            disable_drive_downloads=False,
            disable_source_downloads=False,
            disable_sheet_uploads=True,
            disable_database_uploads=True,
            disable_drive_uploads=True,
            enable_rerun=True,
            force_reprocessing=False,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_DATA: {
                            plugin.CTR_ACT_PREVIOUS_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_CURRENT_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_UPDATE_COLUMNS: fixture["cols_data"],
                            plugin.CTR_ACT_DELTA_COLUMNS: fixture["cols_data"],
                        },
                    },
                    "counter_at_least": {
                        plugin.CTR_SRC_SOURCES: {
                            plugin.CTR_ACT_DOWNLOADED: len(STOCK),
                        },
                        plugin.CTR_SRC_DATA: {
                            plugin.CTR_ACT_DELTA_ROWS: fixture["rows_delta"],
                        },
                    },
                },
            ),
            custom_asserts=[assert_custom_rows_delta(at_least=fixture["rows_delta"])],
            file_asserts={
                "__equity_current*.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="1982-04-01", end_date_at_least=fixture["end_date"], contiguous="days"),
                    assert_file_nones_per_col(after_first_rows=True),
                    assert_file_zeroes_per_row(exclude=r"Market Volume|Change"),
                    assert_file_equal(),
                ],
                "_sheet_prices_history*.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="2007-01-01", end_date_at_least=fixture["end_date"], contiguous="days", descending=True),
                    assert_file_nones_per_col(after_last_rows=True),
                    assert_file_zeroes_per_row(),
                    assert_file_equal(),
                ],
                "_database_equity*.csv": [
                    assert_file_size(),
                    assert_file_nones_per_col(after_first_rows=True),
                    assert_file_subset(),
                ],
            },
        )

    ########################################################################################################################
    # Interest
    ########################################################################################################################

    # No current data, no new data, no remote source data downloads, no remote data repo downloads or uploads
    def test_interest_local_blank_1(self):
        fixture = _load_fixture("local", "interest", "blank_1")
        self.run_plugin(
            "interest",
            plugin.RepoScope.LOCAL,
            "blank_1",
            log_level="info",
            disable_sheet_downloads=True,
            disable_database_downloads=True,
            disable_drive_downloads=True,
            disable_source_downloads=True,
            disable_sheet_uploads=True,
            disable_database_uploads=True,
            disable_drive_uploads=True,
            enable_rerun=False,
            force_reprocessing=False,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_FILES: {
                            plugin.CTR_ACT_ERRORED: fixture["expected_errors"],
                        },
                    },
                },
            ),
            file_asserts={
                "__interest_current.csv": [
                    assert_file_does_not_exist(),
                ],
            },
        )

    # No current data, corrupt data, no remote source data downloads, no remote data repo downloads or uploads
    def test_interest_local_corrupt_1(self):
        fixture = _load_fixture("local", "interest", "corrupt_1")
        self.run_plugin(
            "interest",
            plugin.RepoScope.LOCAL,
            "corrupt_1",
            log_level="fatal",
            disable_sheet_downloads=True,
            disable_database_downloads=True,
            disable_drive_downloads=True,
            disable_source_downloads=True,
            disable_sheet_uploads=True,
            disable_database_uploads=True,
            disable_drive_uploads=True,
            enable_rerun=False,
            force_reprocessing=True,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_FILES: {
                            plugin.CTR_ACT_ERRORED: fixture["expected_errors"],
                        },
                    },
                },
            ),
            file_asserts={
                "__interest_current.csv": [
                    assert_file_does_not_exist(),
                ],
            },
        )

    # No current data, corrupt data, no remote source data downloads, no remote data repo downloads or uploads
    def test_interest_local_corrupt_2(self):
        fixture = _load_fixture("local", "interest", "corrupt_2")
        self.run_plugin(
            "interest",
            plugin.RepoScope.LOCAL,
            "corrupt_2",
            log_level="fatal",
            disable_sheet_downloads=True,
            disable_database_downloads=True,
            disable_drive_downloads=True,
            disable_source_downloads=True,
            disable_sheet_uploads=True,
            disable_database_uploads=True,
            disable_drive_uploads=True,
            enable_rerun=False,
            force_reprocessing=True,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_FILES: {
                            plugin.CTR_ACT_ERRORED: fixture["expected_errors"],
                        },
                    },
                },
            ),
            file_asserts={
                "__interest_current.csv": [
                    assert_file_does_not_exist(),
                ],
            },
        )

    # Lots of current data, a specific amount of new data, no remote source data downloads, downloads and uploads from and to preview data repo
    def test_interest_preview_replete_1(self):
        fixture = _load_fixture("preview", "interest", "replete_1")
        drive_delete(REPOS_INTEREST._scopes["preview"]["drive_folder"], "inflation.xlsx")
        self.run_plugin(
            "interest",
            plugin.RepoScope.PREVIEW,
            "replete_1",
            log_level="info",
            disable_sheet_downloads=True,
            disable_database_downloads=True,
            disable_drive_downloads=False,
            disable_source_downloads=True,
            disable_sheet_uploads=False,
            disable_database_uploads=True,
            disable_drive_uploads=False,
            enable_rerun=True,
            force_reprocessing=False,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_SOURCES: {
                            plugin.CTR_ACT_UPLOADED: 1,
                        },
                        plugin.CTR_SRC_DATA: {
                            plugin.CTR_ACT_PREVIOUS_COLUMNS: len(INTEREST_COLUMNS),
                            plugin.CTR_ACT_CURRENT_COLUMNS: len(INTEREST_COLUMNS),
                            plugin.CTR_ACT_UPDATE_COLUMNS: 0,
                            plugin.CTR_ACT_DELTA_COLUMNS: 0,
                            plugin.CTR_ACT_DELTA_ROWS: 0,
                        },
                    },
                },
            ),
            custom_asserts=[assert_custom_rows_delta(equals=fixture["rows_delta"])],
            file_asserts={
                "__interest_current.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="1982-04-01", end_date=fixture["end_date"], contiguous="months"),
                    assert_file_nones_per_row(exclude=r"Mean"),
                ],
                "_sheet_rates_interest.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="2015-02-01", end_date=fixture["end_date"], contiguous="months", descending=True),
                    assert_file_nones_per_row(exclude=r"Mean"),
                ],
                "_database_interest.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="1982-04-01", end_date=fixture["end_date"], contiguous="months"),
                    assert_file_nones_per_row(exclude=r"type=mean"),
                ],
            },
        )

    # Lots of current data, a lot of live new data, downloads from remote sources, downloads from release data repo, no remote data repo uploads
    def test_interest_release_replete_1(self):
        fixture = _load_fixture("release", "interest", "replete_1")
        self.run_plugin(
            "interest",
            plugin.RepoScope.RELEASE,
            "replete_1",
            log_level="info",
            disable_sheet_downloads=False,
            disable_database_downloads=False,
            disable_drive_downloads=False,
            disable_source_downloads=False,
            disable_sheet_uploads=True,
            disable_database_uploads=True,
            disable_drive_uploads=True,
            enable_rerun=True,
            force_reprocessing=False,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_equals": {
                        plugin.CTR_SRC_DATA: {
                            plugin.CTR_ACT_PREVIOUS_COLUMNS: len(INTEREST_COLUMNS),
                            plugin.CTR_ACT_CURRENT_COLUMNS: len(INTEREST_COLUMNS),
                            plugin.CTR_ACT_UPDATE_COLUMNS: len(INTEREST_COLUMNS),
                            plugin.CTR_ACT_DELTA_COLUMNS: len(INTEREST_COLUMNS),
                        },
                    },
                    "counter_at_least": {
                        plugin.CTR_SRC_DATA: {
                            plugin.CTR_ACT_DELTA_ROWS: fixture["rows_delta"],
                        },
                    },
                },
            ),
            custom_asserts=[assert_custom_rows_delta(at_least=fixture["rows_delta"])],
            file_asserts={
                "__interest_current*.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="1982-04-01", end_date_at_least=fixture["end_date"], contiguous="months"),
                    assert_file_nones_per_row(exclude=r"Mean"),
                    assert_file_equal(),
                ],
                "_sheet_rates_interest*.csv": [
                    assert_file_size(),
                    assert_file_dates(start_date="2015-02-01", end_date_at_least=fixture["end_date"], contiguous="months", descending=True),
                    assert_file_nones_per_row(exclude=r"Mean"),
                    assert_file_equal(),
                ],
                "_database_interest*.csv": [
                    assert_file_size(),
                    assert_file_nones_per_row(exclude=r"type=mean"),
                    assert_file_subset(),
                ],
            },
        )

    ########################################################################################################################
    # Dashboard
    ########################################################################################################################
    def test_dashboard_preview(self):
        def _synthetic_counter_value(action, counter, rand):
            if counter.format == "duration_ms":
                return rand.randint(500, 10000)
            if "Rows" in action:
                return rand.randint(100, 50000)
            if "Columns" in action:
                return rand.randint(5, 30)
            if counter.error:
                return rand.choices([0, 1], weights=[10, 1])[0]
            return rand.randint(0, 50)

        def _synthetic_raw_entry(run_ts, plugin_names, rand):
            run_plugins = {}
            for plugin_key in plugin_names:
                plugin_counters = {}
                for (source_key, action_key), counter in COUNTERS.items():
                    if source_key not in plugin_counters:
                        plugin_counters[source_key] = {}
                    plugin_counters[source_key][action_key] = _synthetic_counter_value(action_key, counter, rand)
                run_plugins[plugin_key] = plugin_counters
            errored = {plugin_id: any(run_plugins[plugin_id].get(source_id, {}).get(action_id, 0) > 0 for (source_id, action_id), c in COUNTERS.items() if c.error) for plugin_id in plugin_names}
            return {
                "ts": run_ts.isoformat(),
                "bucket": int(run_ts.timestamp()) // (30 * 60),
                "plugins": run_plugins,
                "errored": errored,
            }

        def _synthetic_day_entry(date, plugin_names, rand):
            buckets = {}
            errored_runs = {plugin_id: rand.choices([0, 1], weights=[10, 1])[0] for plugin_id in plugin_names}
            for plugin_key in plugin_names:
                buckets[plugin_key] = {}
                for (source_key, action_key), counter in COUNTERS.items():
                    if source_key not in buckets[plugin_key]:
                        buckets[plugin_key][source_key] = {}
                    count = rand.randint(40, 48)
                    tmp_value = _synthetic_counter_value(action_key, counter, rand)
                    buckets[plugin_key][source_key][action_key] = {
                        "sum": tmp_value * count,
                        "min": max(0, tmp_value - 3),
                        "max": tmp_value + 3,
                        "count": count,
                    }
            return {
                "date": date.isoformat(),
                "errored_runs": errored_runs,
                "buckets": buckets,
            }

        plugins = ["bank", "currency", "equity", "interest"]
        all_plugin_names = ["summary"] + sorted(plugins)
        output_dir = abspath(join(DIR_ROOT, "target", "runtime-dashboard"))
        os.makedirs(output_dir, exist_ok=True)
        static_copy = join(output_dir, "static")
        if os.path.islink(static_copy) or os.path.isfile(static_copy):
            os.unlink(static_copy)
        elif os.path.isdir(static_copy):
            shutil.rmtree(static_copy)
        shutil.copytree(STATIC_ROOT_DIR, static_copy)
        rng = random.Random(42)
        with tempfile.TemporaryDirectory() as tmp:
            history = RunHistory(plugins=plugins, cache_dir=tmp, poll_period_minutes=30, raw_label="1d")
            now = datetime.datetime.now(tz=CTR_TZ)
            today = now.date()
            for day_offset in range(HISTORY_AGG_DAY_LENGTH):
                days_ago = HISTORY_AGG_DAY_LENGTH - 1 - day_offset
                if days_ago >= 50 and rng.random() < 0.04:
                    continue
                history._day.append(_synthetic_day_entry(today - datetime.timedelta(days=days_ago), all_plugin_names, rng))
            for run_offset in range(HISTORY_RAW_RUN_LENGTH):
                runs_ago = HISTORY_RAW_RUN_LENGTH - 1 - run_offset
                if 10 <= runs_ago <= 17:
                    continue
                ts = now - datetime.timedelta(minutes=30 * runs_ago)
                history._raw.append(_synthetic_raw_entry(ts, all_plugin_names, rng))
            snapshot = history.snapshot()
            plugin_sections = [
                {"id": "summary", "title": "Summary", "theme": "ghost-gray"},
                *({"id": plugin_name, "title": plugin_name.capitalize(), "theme": THEMES[index % len(THEMES)]} for index, plugin_name in enumerate(p for p in snapshot.plugins if p != "summary")),
            ]
            snapshot_json = json.dumps(dataclasses.asdict(snapshot))
            adhoc_ts = now + datetime.timedelta(minutes=1)
            adhoc_plugins = {}
            for plugin_name in all_plugin_names:
                pcs = {}
                for (src, act), ctr in COUNTERS.items():
                    if src not in pcs:
                        pcs[src] = {}
                    pcs[src][act] = _synthetic_counter_value(act, ctr, rng)
                adhoc_plugins[plugin_name] = pcs
            adhoc_errored = {name: any(adhoc_plugins[name].get(src, {}).get(act, 0) > 0 for (src, act), c in COUNTERS.items() if c.error) for name in all_plugin_names}
            latest_run_json = json.dumps(
                {
                    "ts": adhoc_ts.isoformat(),
                    "plugins": adhoc_plugins,
                    "errored": adhoc_errored,
                }
            )
            html = TEMPLATE.render(
                snapshot_json=snapshot_json,
                latest_run_json=latest_run_json,
                run_timeout_ms=10000,
                views=[{"name": v.name, "label": v.label} for v in snapshot.views],
                chart_spec=CHART_SPEC,
                plugin_sections=plugin_sections,
            )
        output_path = join(output_dir, "dashboard.html")
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(html)
        print(f"\nDashboard preview written to [file://{output_path}]")
        self.assertTrue(isfile(output_path))

    def test_dashboard_history_ignores_different_plugin_scope(self):
        counters = {
            plugin.CTR_SRC_FILES: {
                plugin.CTR_ACT_PROCESSED: 1,
                plugin.CTR_ACT_ERRORED: 0,
            },
            plugin.CTR_SRC_TIMING: {
                plugin.CTR_ACT_PROCESS_MILLIS: 10,
                plugin.CTR_ACT_TOTAL_MILLIS: 10,
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            history = RunHistory(plugins=["bank"], cache_dir=tmp, poll_period_minutes=30, raw_label="1d")
            history.add_run(datetime.datetime.now(tz=CTR_TZ), {"bank": counters})

            filtered_history = RunHistory(plugins=["currency"], cache_dir=tmp, poll_period_minutes=30, raw_label="1d")
            filtered_history.load()

            self.assertEqual(0, len(filtered_history._raw))
            self.assertEqual(0, len(filtered_history._day))

    def test_dashboard_history_retains_when_plugin_added(self):
        counters = {
            plugin.CTR_SRC_FILES: {
                plugin.CTR_ACT_PROCESSED: 1,
                plugin.CTR_ACT_ERRORED: 0,
            },
            plugin.CTR_SRC_TIMING: {
                plugin.CTR_ACT_PROCESS_MILLIS: 10,
                plugin.CTR_ACT_TOTAL_MILLIS: 10,
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            history = RunHistory(plugins=["bank"], cache_dir=tmp, poll_period_minutes=30, raw_label="1d")
            history.add_run(datetime.datetime.now(tz=CTR_TZ), {"bank": counters})

            grown_history = RunHistory(plugins=["bank", "currency"], cache_dir=tmp, poll_period_minutes=30, raw_label="1d")
            grown_history.load()

            self.assertEqual(1, len(grown_history._raw))
            self.assertEqual(1, len(grown_history._day))

            raw_view = grown_history.snapshot().views[0]
            self.assertEqual(1, raw_view.series["bank"][plugin.CTR_SRC_FILES][plugin.CTR_ACT_PROCESSED][0])
            self.assertIsNone(raw_view.series["currency"][plugin.CTR_SRC_FILES][plugin.CTR_ACT_PROCESSED][0])
            self.assertFalse(raw_view.errored["currency"][0])

    def test_dashboard_history_malformed_entries_start_fresh(self):
        counters = {
            plugin.CTR_SRC_FILES: {
                plugin.CTR_ACT_PROCESSED: 1,
                plugin.CTR_ACT_ERRORED: 0,
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            history = RunHistory(plugins=["bank"], cache_dir=tmp, poll_period_minutes=30, raw_label="1d")
            history.add_run(datetime.datetime.now(tz=CTR_TZ), {"bank": counters})

            raw_path = join(tmp, "history_raw.json")
            daily_path = join(tmp, "history_daily.json")
            with open(raw_path, encoding="utf-8") as handle:
                raw_state = json.load(handle)
            raw_state["raw"] = [{"plugins": {}}]
            with open(raw_path, "w", encoding="utf-8") as handle:
                json.dump(raw_state, handle)
            with open(daily_path, encoding="utf-8") as handle:
                daily_state = json.load(handle)
            daily_state["day"] = [{}]
            with open(daily_path, "w", encoding="utf-8") as handle:
                json.dump(daily_state, handle)

            loaded = RunHistory(plugins=["bank"], cache_dir=tmp, poll_period_minutes=30, raw_label="1d")
            loaded.load()

            self.assertEqual(0, len(loaded._raw))
            self.assertEqual(0, len(loaded._day))

    ########################################################################################################################
    # Feeds
    ########################################################################################################################

    def test_feeds_equity_prices(self):
        started = time.time()
        priced = self._feed_live(feeds.equity_prices, "BHP.AX", {})
        self.assertEqual("BHP.AX", priced["symbol"])
        self.assertEqual("AUD", priced["currency"])
        self.assertEqual("ASX", priced["exchange"])
        self.assertIsInstance(priced["price"], float)
        self.assertGreater(priced["price"], 0)
        self.assertGreater(priced["previousClose"], 0)
        self.assertAlmostEqual(priced["price"] - priced["previousClose"], priced["change"], places=3)
        _print_assert_pass("feeds_price_live", f"actual={priced['symbol']}", f"actual={priced['price']}", f"actual={priced['currency']}", f"actual={_format_assert_elapsed(time.time() - started)}")

        for symbol, expected in [("bhp.ax", "BHP.AX"), ("^AXJO", "^AXJO"), ("BRK-B", "BRK-B")]:
            resolved = self._feed_live(feeds.equity_prices, symbol, {})
            self.assertEqual(expected, resolved["symbol"])
            self.assertGreater(resolved["price"], 0)
        _print_assert_pass("feeds_price_tickers", "actual=bhp.ax", "actual=^AXJO", "actual=BRK-B")

        cached_started = time.time()
        cached = feeds.equity_prices("BHP.AX", {})
        cached_elapsed = time.time() - cached_started
        self.assertEqual(priced, cached)
        self.assertLess(cached_elapsed, 0.1)
        parameterised = feeds.equity_prices(None, {"symbol": "BHP.AX"})
        self.assertEqual(priced, parameterised)
        _print_assert_pass("feeds_price_cached", f"actual={_format_assert_elapsed(cached_elapsed)}")

    def test_feeds_errors(self):
        for symbol in ["", "  ", "BHP AX", "'; DROP TABLE", "../../etc/passwd", "A" * 21]:
            with self.assertRaises(feeds.FeedError) as raised:
                feeds.equity_prices(symbol, {})
            self.assertEqual("invalid_symbol", raised.exception.code)
            self.assertEqual(400, raised.exception.status)
        _print_assert_pass("feeds_errors_rejected", "actual=invalid_symbol", "actual=400")

        try:
            with self.assertRaises(feeds.FeedError) as raised:
                feeds.equity_prices("ZZZZQQ.AX", {})
        except AssertionError:
            self.skipTest("yahoo unexpectedly resolved the unknown symbol")
        self.assertEqual("unknown_symbol", raised.exception.code)
        self.assertEqual(404, raised.exception.status)
        self.assertNotIn("exchangeTimezoneName", raised.exception.message)
        _print_assert_pass("feeds_errors_unknown", f"actual={raised.exception.code}", f"actual={raised.exception.status}")

    def test_feeds_routing(self):
        self.assertEqual({"equity.prices": "feed/equity/prices"}, feeds.paths())
        _resource, argument = feeds.resolve("equity/prices/BHP.AX")
        self.assertEqual("BHP.AX", argument)
        with mock.patch.dict(feeds.FEEDS, {"equity": {"prices": lambda captured, params: {"argument": captured, "params": params}}}):
            bound, _ = feeds.resolve("equity/prices/VAS.AX")
            self.assertEqual({"argument": "VAS.AX", "params": {"q": "x"}}, bound({"q": "x"}))
            bound, argument = feeds.resolve("equity/prices")
            self.assertIsNone(argument)
            self.assertEqual({"argument": None, "params": {}}, bound({}))
        for path, code in [("equity", "not_found"), ("", "not_found"), ("equity/prices/A/B", "not_found"), ("crypto/prices", "unknown_feed"), ("equity/nope", "unknown_resource")]:
            with self.assertRaises(feeds.FeedError) as raised:
                feeds.resolve(path)
            self.assertEqual(code, raised.exception.code)
            self.assertEqual(404, raised.exception.status)
        _print_assert_pass("feeds_routing", f"actual={len(feeds.FEEDS)}", "actual=unknown_feed", "actual=unknown_resource")

    def _feed_live(self, resource, argument, params):
        try:
            return resource(argument, params)
        except feeds.FeedError as error:
            if error.code == "upstream_error":
                self.skipTest(f"yahoo unreachable [{error.message}]")
            raise

    ########################################################################################################################
    # Sources
    ########################################################################################################################

    def test_library_sheet(self):
        test = PluginStub("Test", "SOME_NON_EXISTANT_GUID")

        def _sheet_read(_result, schema=None):
            if schema is None:
                schema = {}
            if _result.file_status == DownloadStatus.FAILED:
                return test.dataframe_new()
            return test.csv_read(_result.file_paths[0], schema=schema)

        plugin.config.log_level = "fatal"
        missing = test.sheet_download("!", "missing", sheet_load_secs=0, sheet_retry_max=1)
        self.assertEqual(DownloadStatus.FAILED, missing.file_status)
        self.assertEqual(0, len(_sheet_read(missing)))
        loading = test.sheet_download("1bUpZCIOM-olcxLQ7_fdgi4Nu7GOQC30sK_LALZ2B0bs", "loading", sheet_load_secs=0, sheet_retry_max=1)
        self.assertEqual(DownloadStatus.FAILED, loading.file_status)
        self.assertEqual(0, len(_sheet_read(loading)))

        plugin.config.log_level = "info"
        empty = test.sheet_download("1nPtCOciS81Y-FWJZ8pi5-9Fd6RZ6_EqyfweBekFH6s4", "empty")
        self.assertEqual(DownloadStatus.DOWNLOADED, empty.file_status)
        self.assertEqual("[]", test.dataframe_to_str(_sheet_read(empty)))
        self.assertEqual("[]", test.dataframe_to_str(_sheet_read(empty, schema={"My Column": pl.Utf8})))

        test_type_number = {
            "Integer": pl.Int64,
            "Integer with NULL": pl.Int64,
            "Float": pl.Float64,
            "Float with NULL": pl.Float64,
            "String": pl.Utf8,
            "String with NULL": pl.Utf8,
        }
        test_type_utf = dict.fromkeys(test_type_number, pl.Utf8)
        test_str = "[Integer({}), Integer with NULL({}), Float({}), Float with NULL({}), String({}), String with NULL({})]"
        typed = test.sheet_download("18MBAIWaQNVQBMESAISHIqLD11sRBz003x5OTH_Vt4SY", "test", sheet_start_row=3)
        self.assertEqual(DownloadStatus.DOWNLOADED, typed.file_status)
        typed_number = _sheet_read(typed, schema=test_type_number)
        self.assertEqual(test_str.format(*[test.dataframe_type_to_str(dtype) for dtype in test_type_number.values()]), test.dataframe_to_str(typed_number))
        self.assertEqual(4, len(typed_number))
        typed_utf = _sheet_read(typed, schema=test_type_utf)
        self.assertEqual(test_str.format(*["String" for _ in test_type_utf]), test.dataframe_to_str(typed_utf))
        self.assertEqual(4, len(typed_utf))

        data_key = "1Kf9-Gk7aD4aBdq2JCfz5zVUMWAtvJo2ZfqmSQyo8Bjk"
        data_str = "[Exchange Symbol(String), Port Quantity({}), Unit Price(Float64), Watch Value(Float64), Watch Quantity(Int64), Base Quantity(Int64)]"
        download = test.sheet_download(data_key, "Index_weights", "Indexes", 2, check=True)
        self.assertEqual(DownloadStatus.DOWNLOADED, download.file_status)
        validated = test.sheet_download(data_key, "Index_weights", "Indexes", 2, check=True)
        self.assertEqual(DownloadResult(DownloadStatus.CACHED, download.file_paths), validated)
        blind = test.sheet_download(data_key, "Index_weights", "Indexes", 2, check=False)
        self.assertEqual(DownloadResult(DownloadStatus.CACHED, download.file_paths), blind)
        plugin.config.force_downloads = True
        forced = test.sheet_download(data_key, "Index_weights", "Indexes", 2, check=False)
        self.assertEqual(DownloadResult(DownloadStatus.CACHED, download.file_paths), forced)
        plugin.config.force_downloads = False
        data_df = _sheet_read(download)
        self.assertEqual(data_str.format("Float64"), test.dataframe_to_str(data_df))
        self.assertEqual(24, len(data_df))
        data_df = _sheet_read(download, schema={"Port Quantity": pl.Utf8})
        self.assertEqual(data_str.format(test.dataframe_type_to_str(pl.Utf8)), test.dataframe_to_str(data_df))
        self.assertEqual(24, len(data_df))

        batch = test.sheet_download(data_key, "Index_weights", ["Indexes", "Absent"], 2, schema={"Exchange Symbol": pl.Utf8, "Unit Price": pl.Float64})
        self.assertEqual({"Indexes": DownloadStatus.DOWNLOADED, "Absent": DownloadStatus.DOWNLOADED}, {tab: result.file_status for tab, result in batch.items()})
        self.assertEqual(24, len(test.csv_read(batch["Indexes"].file_paths[0])))
        self.assertEqual(0, len(test.csv_read(batch["Absent"].file_paths[0])))
        self.assertEqual(
            {"Indexes": DownloadStatus.CACHED, "Absent": DownloadStatus.CACHED},
            {
                tab: result.file_status
                for tab, result in test.sheet_download(data_key, "Index_weights", ["Indexes", "Absent"], 2, schema={"Exchange Symbol": pl.Utf8, "Unit Price": pl.Float64}).items()
            },
        )

    def test_bank_flag(self):
        values = ["Yes", " yes ", "YES", "No", "no\t", " NO", "y", "", None, "true", "Yes No"]
        self.assertEqual(
            ["Yes", "Yes", "Yes", "No", "No", "No", None, None, None, None, None], pl.DataFrame({"Value": values}, schema={"Value": pl.Utf8}).select(bank_flag("Value"))["Value"].to_list()
        )

    def test_bank_tab_edits(self):
        test = PluginStub("Test", "SOME_NON_EXISTANT_GUID")
        columns = [
            "Date",
            "Account",
            "Amount",
            "Amount Split",
            "Description",
            "Vetted",
            "Category Manual",
            "Category",
            "Category Auto",
            "Bucket",
            "Notes",
            "Account ID",
            "Source ID",
            "Transaction ID",
        ]
        base = [
            ["2026-01-02", "One", "-10.0", "-10.0", "Shop", "", "", "Food", "Food", "Living", "", "a1", "s1", "t1"],
            ["2026-01-03", "One", "-20.0", "-20.0", "Fuel", "Yes", "", "Car", "Car", "Costs", "", "a1", "s2", "t2"],
            ["2026-01-04", "One", "-30.0", "-30.0", "Rent", "No", "", "", "", "", "", "a1", "", "t3"],
        ]

        def _tab(_rows, _columns=None):
            return test.sheet_typed(pl.DataFrame(_rows, schema=dict.fromkeys(_columns or columns, pl.Utf8), orient="row"), TRANSACTIONS_YEAR_TAB_SCHEMA)

        def _edited(_rows, _column, _value, _index=0):
            _rows = copy.deepcopy(_rows)
            _rows[_index][columns.index(_column)] = _value
            return _rows

        def _parts(*_parts):
            return [{"Amount Split": split, "Category Manual": manual, "Vetted": vetted, "Notes": notes} for split, manual, vetted, notes in _parts]

        for label, tab_rows, tab_columns, expected in [
            ("unchanged", base, None, ({}, 0, 0)),
            ("sorted", list(reversed(base)), None, ({}, 0, 0)),
            ("restyled", [[*row[:2], "$" + row[2].replace(".0", ".00"), *row[3:]] for row in base], None, ({}, 0, 0)),
            ("category manual", _edited(base, "Category Manual", "Groceries"), None, ({"t1": _parts((-1000, "Groceries", None, None))}, 0, 0)),
            ("vetted", _edited(base, "Vetted", " yes "), None, ({"t1": _parts((-1000, None, "Yes", None))}, 0, 0)),
            ("vetted cleared", _edited(base, "Vetted", "", 1), None, ({"t2": _parts((-2000, None, None, None))}, 0, 0)),
            ("notes", _edited(base, "Notes", "Gift for Sam"), None, ({"t1": _parts((-1000, None, None, "Gift for Sam"))}, 0, 0)),
            ("split", [*_edited(base, "Amount Split", "-4.0"), _edited(base, "Amount Split", "-6.0")[0]], None, ({"t1": _parts((-400, None, None, None), (-600, None, None, None))}, 0, 0)),
            ("formula", _edited(_edited(base, "Category", "Other"), "Bucket", "Elsewhere"), None, ({}, 0, 0)),
            ("description", _edited(base, "Description", "Shop Two"), None, ({}, 1, 0)),
            ("description and vetted", _edited(_edited(base, "Description", "Shop Two"), "Vetted", "Yes"), None, ({"t1": _parts((-1000, None, "Yes", None))}, 1, 0)),
            ("idless", [*base, ["2026-01-05", "Cash", "-1.0", "", "Typed", "", "", "", "", "", "", "", "", ""]], None, ({}, 0, 1)),
            ("cut short", base[:1], None, ({}, 0, 0)),
            (
                "without vetted",
                [[*row[:5], *row[6:]] for row in _edited(base, "Category Manual", "Groceries")],
                [column for column in columns if column != "Vetted"],
                ({"t1": _parts((-1000, "Groceries", None, None))}, 0, 0),
            ),
        ]:
            edits, ignored, idless = bank_tab_edits(_tab(tab_rows, tab_columns), _tab(base))
            self.assertEqual(expected, ({transaction_id: edit["Tab"] for transaction_id, edit in edits.items()}, ignored, idless), label)
        edits, _, _ = bank_tab_edits(_tab(_edited(base, "Vetted", "maybe")), _tab(base))
        self.assertEqual("maybe", edits["t1"]["Bad Vetted"])
        edits, _, _ = bank_tab_edits(_tab([[*row[:5], *row[6:]] for row in _edited(base, "Category Manual", "Groceries")], [column for column in columns if column != "Vetted"]), _tab(base))
        self.assertEqual(["Amount Split", "Category Manual", "Notes"], edits["t1"]["Present"])

    def test_bank_export_parsed(self):
        header = "Date,Date Processed,Description,Card Member,Account #,Amount"
        for label, content, expected in [
            (
                "credit and charge",
                f"\ufeff{header}\r\n14/01/2026,15/01/2026,CAFE  ONE  ,A MEMBER,-00001,4.50\r\n13/01/2026,14/01/2026,REFUND,B MEMBER,-00002,-20.00",
                ([("2026-01-14", "2026-01-15", -4.5, "CAFE  ONE", "-00001"), ("2026-01-13", "2026-01-14", 20.0, "REFUND", "-00002")], 0),
            ),
            ("dollars and pending", f'{header}\n02/01/2026,,PENDING,A,-00001,1.00\n03/01/2026,04/01/2026,BIG,A,-00001,"$1,234.50"\n', ([("2026-01-03", "2026-01-04", -1234.5, "BIG", "-00001")], 1)),
            ("empty", f"{header}\n", ([], 0)),
        ]:
            parsed_df, pending = bank_export_parsed(content.encode())
            self.assertEqual(expected, ([(str(row[0]), str(row[1]), row[2], row[3], row[4]) for row in parsed_df.rows()], pending), label)
        for label, content in [
            ("header", "Date,Description,Amount\n14/01/2026,X,1.00\n"),
            ("date", f"{header}\n2026-01-14,15/01/2026,X,A,-00001,1.00\n"),
            ("month", f"{header}\n01/13/2026,15/01/2026,X,A,-00001,1.00\n"),
            ("decimals", f"{header}\n14/01/2026,15/01/2026,X,A,-00001,1.005\n"),
            ("amount", f"{header}\n14/01/2026,15/01/2026,X,A,-00001,lots\n"),
            ("cells", f"{header}\n14/01/2026,15/01/2026,X,A,1.00\n"),
        ]:
            with self.assertRaises(ValueError, msg=label):
                bank_export_parsed(content.encode())

    def test_bank_export_account(self):
        export_df = pl.DataFrame(
            [(date_type(2026, 1, day), -float(day), f"SHOP  {day}", card) for day, card in ((1, "-00001"), (2, "-00002"), (3, "-00001"), (20, "-00001"))],
            schema={"Date": pl.Date, "Amount": pl.Float64, "Description": pl.Utf8, "Card": pl.Utf8},
            orient="row",
        )
        accounts_df = pl.DataFrame({"Account ID": ["x", "y"]})

        def _held(_rows):
            return pl.DataFrame(_rows, schema={"Account ID": pl.Utf8, "Date": pl.Date, "Amount": pl.Float64, "Description": pl.Utf8}, orient="row")

        overlap = [("x", date_type(2026, 1, 1), -1.0, "SHOP 1"), ("x", date_type(2026, 1, 3), -3.0, "SHOP 3"), ("x", date_type(2026, 1, 5), -9.0, "OTHER")]
        for label, cards, held, expected in [
            ("card", {"-00002": "y"}, overlap, ("y", "card")),
            ("cards of two accounts", {"-00001": "x", "-00002": "y"}, overlap, (None, "cards of more than one account")),
            ("overlap", {}, overlap, ("x", "overlap")),
            ("overlap split", {}, [*overlap, ("y", date_type(2026, 1, 2), -2.0, "SHOP 2"), ("y", date_type(2026, 1, 3), -3.0, "SHOP 3")], (None, "overlap with more than one account")),
            ("new card, no overlap", {"-00009": "x"}, [("x", date_type(2026, 1, 1), -5.0, "ELSE")], (None, "no overlap")),
            ("nothing held", {}, [], (None, "no overlap")),
        ]:
            self.assertEqual(expected, bank_export_account(export_df, cards, accounts_df, _held(held)), label)

    def test_library_sheet_ensure(self):
        test = PluginStub("Test", "SOME_NON_EXISTANT_GUID")

        class _Worksheet:
            def __init__(self, title):
                self.title = title
                self.values = None

            def update(self, values, range_name):
                self.values = (range_name, values)

        class _Spreadsheet:
            def __init__(self, titles):
                self.sheets = [_Worksheet(title) for title in titles]

            def worksheets(self):
                return list(self.sheets)

            def add_worksheet(self, title, rows, cols, index=None):
                worksheet = _Worksheet(title)
                self.sheets.insert(len(self.sheets) if index is None else index, worksheet)
                return worksheet

        tabs = {"Summary": [], "Logs": ["Date", "Kind"], "Classifier": ["Category"], "Accounts": ["From", "Name"], "Balances": ["Date"], "Transactions": ["End of Month"]}
        for titles, expected_titles, expected_created in [
            ([], list(tabs), list(tabs)),
            (
                ["Accounts", "Transactions_2026", "Transactions_2025", "Custom"],
                ["Summary", "Logs", "Classifier", "Accounts", "Balances", "Transactions", "Transactions_2026", "Transactions_2025", "Custom"],
                ["Summary", "Logs", "Classifier", "Balances", "Transactions"],
            ),
            (list(tabs), list(tabs), []),
        ]:
            spreadsheet = _Spreadsheet(titles)
            test._sheet_worksheets = {}
            mock.patch.object(Plugin, "_sheet_opened", lambda _self, _key, _spreadsheet=spreadsheet: (_spreadsheet, None)).start()
            plugin.config.disable_sheet_uploads = False
            self.assertEqual(expected_created, test.sheet_ensure("key", "Test", tabs))
            self.assertEqual(expected_titles, [worksheet.title for worksheet in spreadsheet.sheets])
            created = {worksheet.title: worksheet.values for worksheet in spreadsheet.sheets if worksheet.title in expected_created}
            self.assertEqual({name: None if not tabs[name] else ("A1", [tabs[name]]) for name in expected_created}, created)
            mock.patch.stopall()
        plugin.config.disable_sheet_uploads = True
        self.assertEqual([], test.sheet_ensure("key", "Test", tabs))

    def test_library_redbark_download(self):
        test = PluginStub("Test", "SOME_NON_EXISTANT_GUID")
        local_path = join(DIR_ROOT, "target", "data", "_redbark_things.csv")
        columns = ["id", "amount", "absent"]
        rows = [{"id": "r1", "amount": 7, "extra": "x"}, {"id": "r2", "amount": -1.5}, {"id": "r3", "amount": None}]
        requested = []

        def _urlopen(request, *_args, **_kwargs):
            requested.append(request.full_url)
            url = urllib.parse.urlparse(request.full_url)
            query = {key: values[0] for key, values in urllib.parse.parse_qs(url.query).items()}
            if url.path in ("/v1/fail", "/v1/gone"):
                raise urllib.error.HTTPError(request.full_url, 500 if url.path == "/v1/fail" else 404, "offline fixture error", Message(), None)
            offset, limit = int(query.get("offset", 0)), int(query.get("limit", len(rows)))
            page = {"/v1/things": rows[offset : offset + limit], "/v1/empty": [], "/v1/endless": rows[:1]}[url.path]
            has_more = url.path != "/v1/things" or offset + limit < len(rows)
            return urllib.response.addinfourl(io.BytesIO(json.dumps({"data": page, "pagination": {"hasMore": has_more}}).encode()), Message(), request.full_url, 200)

        def _counters():
            return [test.get_counter(plugin.CTR_SRC_SOURCES, action) for action in (plugin.CTR_ACT_DOWNLOADED, plugin.CTR_ACT_CACHED, plugin.CTR_ACT_ERRORED, plugin.CTR_ACT_SKIPPED)]

        mock.patch("wrangle.plugin._sources.urllib.request.urlopen", _urlopen).start()
        mock.patch("wrangle.plugin._sources.REDBARK_PAGE_LIMIT", 1).start()
        mock.patch("wrangle.plugin._sources.REDBARK_PAGES_MAX", 5).start()
        plugin.config.disable_source_downloads = False
        plugin.config.force_downloads = False
        plugin.config.force_reprocessing = False
        expected = [("r1", "7", None), ("r2", "-1.5", None), ("r3", None, None)]

        result = test.redbark_download(["/v1/things"], local_path, columns)
        self.assertEqual((DownloadStatus.DOWNLOADED, [local_path], ()), (result.file_status, result.file_paths, result.errors))
        assert result.data_frame is not None
        self.assertEqual(expected, result.data_frame.rows())
        self.assertEqual(expected, pl.read_csv(local_path, infer_schema=False).select(columns).rows())
        self.assertEqual(3, len(requested))
        self.assertEqual([1, 0, 0, 0], _counters())

        requested.clear()
        result = test.redbark_download(["/v1/things?from=2026-01-01"], local_path, columns, paged=False)
        assert result.data_frame is not None
        self.assertEqual((DownloadStatus.DOWNLOADED, 3), (result.file_status, len(result.data_frame)))
        self.assertEqual(["https://api.redbark.com/v1/things?from=2026-01-01"], requested)

        pl.DataFrame({"id": ["cached"], "amount": ["1"]}).write_csv(local_path)
        os.utime(local_path, (0, 0))
        result = test.redbark_download(["/v1/things", "/v1/gone"], local_path, columns, ignore=True)
        self.assertEqual((DownloadStatus.FAILED, []), (result.file_status, result.file_paths))
        assert result.data_frame is not None
        self.assertEqual(expected, result.data_frame.rows())
        self.assertEqual([("/v1/gone", 404)], [(error["Path"], error["Status"]) for error in result.errors])
        self.assertEqual((0, [("cached", "1")]), (int(getmtime(local_path)), pl.read_csv(local_path, infer_schema=False).rows()))
        self.assertEqual([2, 0, 0, 0], _counters())

        result = test.redbark_download(["/v1/fail", "/v1/empty", "/v1/endless"], local_path, columns)
        self.assertEqual((DownloadStatus.FAILED, None), (result.file_status, result.data_frame))
        self.assertEqual([("/v1/fail", 500), ("/v1/empty", None), ("/v1/endless", None)], [(error["Path"], error["Status"]) for error in result.errors])
        self.assertEqual([2, 0, 1, 0], _counters())

        requested.clear()
        result = test.redbark_download(["/v1/things"], local_path, columns, check=False)
        assert result.data_frame is not None
        self.assertEqual((DownloadStatus.CACHED, [local_path], [("cached", "1", None)]), (result.file_status, result.file_paths, result.data_frame.rows()))
        self.assertEqual([], requested)
        plugin.config.force_downloads = True
        self.assertEqual(DownloadStatus.DOWNLOADED, test.redbark_download(["/v1/things"], local_path, columns, check=False).file_status)
        plugin.config.force_downloads = False

        plugin.config.disable_source_downloads = True
        self.assertEqual(DownloadStatus.CACHED, test.redbark_download(["/v1/things"], local_path, columns).file_status)
        os.remove(local_path)
        self.assertEqual(DownloadStatus.FAILED, test.redbark_download(["/v1/things"], local_path, columns).file_status)
        plugin.config.force_reprocessing = True
        self.assertEqual(DownloadStatus.SKIPPED, test.redbark_download(["/v1/things"], local_path, columns).file_status)
        self.assertEqual([3, 2, 1, 1], _counters())

    def test_library_sheet_insert_index(self):
        titles = ["Summary", "Logs", "Transactions", "Transactions_2026", "Transactions_2024", "Accounts"]
        for before, after, expected in [
            (None, None, None),
            (["Missing"], ["Absent"], None),
            (["Transactions_2026", "Transactions_2024"], None, 3),
            (["Transactions_2024", "Transactions_2026"], None, 3),
            (["Transactions_2024"], ["Transactions", "Transactions_2026"], 4),
            (["Transactions_2026", "Transactions_2024"], ["Transactions"], 3),
            (["Transactions_2024"], ["Missing"], 4),
            (None, ["Accounts"], 6),
        ]:
            self.assertEqual(expected, Plugin._sheet_insert_index(titles, before, after), f"before {before} after {after}")

    def test_library_sheet_format(self):
        test = PluginStub("Test", "SOME_NON_EXISTANT_GUID")
        data_df = pl.DataFrame({"Amount": [1.0, 2.0], "Amount Manual": [None, 3.0], "Amount Linked": [1.0, None], "Note": ["=a", "1,000"]})
        test.sheet_upload(
            data_df,
            None,
            "Format",
            sheet_name="Tab",
            raw_columns=["Note", "Amount"],
            formula_columns={"Amount": '=IF({Amount Manual}<>"",{Amount Manual},{Amount Linked})'},
            dropdown_columns={"Note": "Options!A2:A"},
            highlight_cells=["B", "A2:D2"],
        )
        with open(join(test.local_cache, "_sheet_format_tab_format.json")) as format_file:
            self.assertEqual(
                {"raw": ["Note"], "formulas": {"Amount": '=IF({Amount Manual}<>"",{Amount Manual},{Amount Linked})'}, "dropdowns": {"Note": "Options!A2:A"}, "highlights": ["B", "A2:D2"]},
                json.load(format_file),
            )
        self.assertEqual(0, test.get_counter(plugin.CTR_SRC_EGRESS, plugin.CTR_ACT_ERRORED))
        test.sheet_upload(
            data_df, None, "Format", sheet_name="Tab", raw_columns=["Missing"], formula_columns={"Amount": "={Missing}"}, dropdown_columns={"Missing": "Options!A2:A"}, highlight_cells=["Z9", "bad"]
        )
        with open(join(test.local_cache, "_sheet_format_tab_format.json")) as format_file:
            self.assertEqual({"raw": [], "formulas": {}, "dropdowns": {}, "highlights": []}, json.load(format_file))
        self.assertEqual(5, test.get_counter(plugin.CTR_SRC_EGRESS, plugin.CTR_ACT_ERRORED))
        self.assertEqual(["_sheet_format_tab_v1.csv", "_sheet_format_tab_v2.csv"], sorted(basename(path) for path in glob.glob(join(test.local_cache, "_sheet_format_tab_v*.csv"))))
        test.sheet_upload(data_df, None, "Format", sheet_name="Tab", dropdown_columns={"Note": ["Yes", "No"], "Amount": [], "Amount Manual": ["Yes", ""]})
        with open(join(test.local_cache, "_sheet_format_tab_format.json")) as format_file:
            self.assertEqual({"raw": [], "formulas": {}, "dropdowns": {"Note": ["Yes", "No"]}, "highlights": []}, json.load(format_file))
        self.assertEqual(7, test.get_counter(plugin.CTR_SRC_EGRESS, plugin.CTR_ACT_ERRORED))

    def test_library_sheet_versions(self):
        test = PluginStub("Test", "SOME_NON_EXISTANT_GUID")
        tabs = {"Tab": [["Date", "Amount", "Note"], ["2026-01-02", "1234.0", "a"]], "Other": [["Name"], ["x"]]}
        reads = []

        def _values(_self, _key, _titles):
            reads.append(list(_titles))
            return {title: copy.deepcopy(tabs[title]) for title in _titles if title in tabs}

        mock.patch.object(Plugin, "_sheet_values", _values).start()
        plugin.config.disable_sheet_downloads = False
        schema = {"Date": pl.Date, "Amount": pl.Float64, "Note": pl.Utf8, "Name": pl.Utf8}

        def _statuses(_results):
            return {tab: (result.file_status, basename(result.file_paths[0]) if result.file_paths else None) for tab, result in _results.items()}

        self.assertEqual(
            {
                "Tab": (DownloadStatus.DOWNLOADED, "_sheet_book_tab_v1.csv"),
                "Other": (DownloadStatus.DOWNLOADED, "_sheet_book_other_v1.csv"),
                "Absent": (DownloadStatus.DOWNLOADED, "_sheet_book_absent_v1.csv"),
            },
            _statuses(test.sheet_download("key", "Book", ["Tab", "Other", "Absent"], schema=schema)),
        )
        tabs["Tab"][1] = ["02/01/2026", "$1,234.00", " a "]
        self.assertEqual({"Tab": (DownloadStatus.CACHED, "_sheet_book_tab_v1.csv")}, _statuses(test.sheet_download("key", "Book", ["Tab"], schema=schema)))
        tabs["Tab"][1] = ["2026-01-02", "1234.5", "a"]
        self.assertEqual({"Tab": (DownloadStatus.DOWNLOADED, "_sheet_book_tab_v2.csv")}, _statuses(test.sheet_download("key", "Book", ["Tab"], schema=schema)))
        self.assertEqual(DownloadStatus.CACHED, test.sheet_download("key", "Book", "Tab", schema=schema).file_status)
        self.assertEqual(DownloadStatus.CACHED, test.sheet_download("key", "Book", "Tab", schema=schema, check=False).file_status)
        self.assertEqual(4, len(reads))
        upload_df = pl.DataFrame({"Date": [date_type(2026, 1, 3)], "Amount": [7.0], "Note": ["b"]})
        self.assertEqual(plugin.UploadStatus.UPLOADED, test.sheet_upload(upload_df, None, "Book", sheet_name="Tab", schema=schema))
        self.assertEqual(["_sheet_book_tab_v2.csv", "_sheet_book_tab_v3.csv"], sorted(basename(path) for path in glob.glob(join(test.local_cache, "_sheet_book_tab_v*.csv"))))
        self.assertEqual(plugin.UploadStatus.UNCHANGED, test.sheet_upload(upload_df, None, "Book", sheet_name="Tab", schema=schema))
        tabs["Tab"][1] = ["03/01/2026", "7", "b"]
        self.assertEqual(plugin.UploadStatus.UPLOADED, test.sheet_upload(upload_df.with_columns(pl.lit("c").alias("Note")), "key", "Book", sheet_name="Tab", schema=schema, guard=True))
        tabs["Tab"][1] = ["03/01/2026", "8", "c"]
        self.assertEqual(plugin.UploadStatus.MOVED, test.sheet_upload(upload_df, "key", "Book", sheet_name="Tab", schema=schema, guard=True))
        self.assertEqual(plugin.UploadStatus.UPLOADED, test.sheet_upload(upload_df.clear(), None, "Book", sheet_name="Empty", schema=schema))
        tabs["Empty"] = [["Date", "Amount", "Note"]]
        self.assertEqual(DownloadStatus.CACHED, test.sheet_download("key", "Book", "Empty", schema=schema).file_status)
        self.assertEqual(plugin.UploadStatus.UPLOADED, test.sheet_upload(upload_df, "key", "Book", sheet_name="Empty", schema=schema, guard=True))
        plugin.config.disable_sheet_downloads = True
        self.assertEqual({"Tab": DownloadStatus.CACHED, "Missing": DownloadStatus.FAILED}, {tab: result.file_status for tab, result in test.sheet_download("key", "Book", ["Tab", "Missing"]).items()})

    def test_library_drive_synchronise(self):
        test = PluginStub("Test", "folder")
        test.drive_download_only = ("activity*.csv",)
        test.error_codes = {"DRIVE_CONFLICT": (plugin.LOG_KIND_ERROR, False, True, plugin.CTR_SRC_SOURCES), "DRIVE_DUPLICATE": (plugin.LOG_KIND_ERROR, False, False, plugin.CTR_SRC_SOURCES)}
        plugin.config.repo_scope = plugin.RepoScope.RELEASE
        plugin.config.disable_drive_downloads = False
        plugin.config.disable_drive_uploads = False
        drive = _FakeDrive()
        drive.put("a.csv", b"1")
        drive.put("dup.csv", b"x")
        drive.put("dup.csv", b"y")
        same_ids = [drive.put("same.csv", b"s"), drive.put("same.csv", b"s")]
        activity_ids = [drive.put("activity.csv", b"e1"), drive.put("activity.csv", b"e2")]
        drive.patch()
        errors = []

        def _sync(download=True, upload=False):
            return {basename(path): str(status) for path, status in test.drive_synchronise("folder", test.local_cache, download=download, upload=upload, errors=errors).items()}

        def _local(name):
            with open(join(test.local_cache, name), "rb") as local_file:
                return local_file.read()

        def _write(name, content):
            with open(join(test.local_cache, name), "wb") as local_file:
                local_file.write(content)

        def _codes():
            codes = sorted({error["Code"] for error in errors})
            errors.clear()
            return codes

        activity_names = [f"activity_{drive_id.lower()}.csv" for drive_id in activity_ids]
        self.assertEqual({"a.csv": "downloaded", "same.csv": "downloaded", **dict.fromkeys(activity_names, "downloaded")}, _sync())
        self.assertEqual(["DRIVE_DUPLICATE"], _codes())
        self.assertFalse(isfile(join(test.local_cache, "dup.csv")))
        self.assertEqual(([same_ids[0]], b"s"), (drive.live("same.csv"), _local("same.csv")))
        self.assertEqual(2, len(drive.live("dup.csv")))
        self.assertEqual({"a.csv": "cached", "same.csv": "cached", **dict.fromkeys(activity_names, "cached")}, _sync())
        drive.put("a.csv", b"2")
        self.assertEqual("downloaded", _sync()["a.csv"])
        self.assertEqual(b"2", _local("a.csv"))
        _write("a.csv", b"local")
        drive.put("a.csv", b"3")
        self.assertEqual("conflicted", _sync()["a.csv"])
        self.assertEqual((b"3", ["DRIVE_CONFLICT", "DRIVE_DUPLICATE"]), (_local("a.csv"), _codes()))
        _write("a.csv", b"4")
        _write("b.csv", b"new")
        _write(activity_names[0], b"edited")
        self.assertEqual({"a.csv": "uploaded", "b.csv": "uploaded"}, {name: status for name, status in _sync(download=False, upload=True).items() if name in ("a.csv", "b.csv")})
        self.assertEqual((b"4", b"new", b"e1"), (drive.content("a.csv"), drive.content("b.csv"), drive.content_by_id(activity_ids[0])))
        self.assertEqual("verified", _sync(download=False, upload=True)["a.csv"])
        _write("c.csv", b"c")
        drive.after_list.append(lambda: drive.put("c.csv", b"other writer"))
        self.assertEqual("uploaded", _sync(download=False, upload=True)["c.csv"])
        self.assertEqual((1, b"c"), (len(drive.live("c.csv")), drive.content("c.csv")))
        _write("a.csv", b"5")
        drive.put("a.csv", b"6")
        self.assertEqual("conflicted", _sync(download=False, upload=True)["a.csv"])
        self.assertEqual((b"6", ["DRIVE_CONFLICT"]), (drive.content("a.csv"), _codes()))
        self.assertTrue(test.drive_rename("folder", test.local_cache, activity_names[1], "amex_xxxx0001_transactions_2026-01-31.csv"))
        self.assertEqual("amex_xxxx0001_transactions_2026-01-31.csv", drive.name_by_id(activity_ids[1]))
        self.assertTrue(isfile(join(test.local_cache, "amex_xxxx0001_transactions_2026-01-31.csv")))
        with open(join(test.local_cache, "_drive_synced.json")) as manifest_file:
            manifest = json.load(manifest_file)
        self.assertIn("amex_xxxx0001_transactions_2026-01-31.csv", manifest)
        self.assertNotIn(activity_names[1], manifest)
        os.remove(join(test.local_cache, "_drive_synced.json"))
        self.assertEqual("cached", _sync()["b.csv"])
        with open(join(test.local_cache, "_drive_synced.json")) as manifest_file:
            self.assertIn("b.csv", json.load(manifest_file))

    def test_library_throttle(self):
        waits = []
        mock.patch("wrangle.plugin._throttle.time.sleep", waits.append).start()

        def _sent(_responses):
            def _send():
                status, headers = _responses.pop(0) if len(_responses) > 1 else _responses[0]
                message = Message()
                for key, value in headers.items():
                    message[key] = value
                if status != 200:
                    raise urllib.error.HTTPError("https://example", status, "offline fixture error", message, None)
                return urllib.response.addinfourl(io.BytesIO(b"{}"), message, "https://example", 200)

            return _send

        for label, calls, expected_waits, expected_raised in [
            ("retry after then backoff", [[(429, {"Retry-After": "2"}), (503, {}), (200, {})]], [2, 10], [False]),
            ("retry after as a date", [[(429, {"Retry-After": "Thu, 01 Jan 2099 00:00:00 GMT"}), (200, {})]], [60], [False]),
            ("not retried", [[(500, {}), (200, {})]], [], [True]),
            ("reset waited before the next call", [[(200, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "3"})], [(200, {})]], [3], [False, False]),
            ("retries exhausted", [[(429, {})]], [5, 10, 20, 40], [True]),
            ("budget shared by calls", [[(429, {})]] * 4, [5, 10, 20, 40, 5, 10, 20, 40, 5, 10, 15], [True] * 4),
        ]:
            waits.clear()
            throttle = Throttle("test", plugin.REDBARK_BACKOFF, lambda *_args, **_kwargs: None)
            raised = []
            for responses in calls:
                try:
                    throttle.call(_sent(list(responses)), urllib_failed)
                    raised.append(False)
                except urllib.error.HTTPError:
                    raised.append(True)
            self.assertEqual((expected_waits, expected_raised), ([round(wait) for wait in waits], raised), label)
        throttle.reset()
        self.assertEqual((0.0, 0.0), (throttle.waited, throttle.resume))

    def test_library_throttle_adapters(self):
        def _google(_status, _reason=None, _retry=None):
            content = json.dumps({"error": {"code": _status, "message": "m", "errors": [{"reason": _reason}] if _reason else []}}).encode()
            return googleapiclient.errors.HttpError(httplib2.Response({"status": _status, **({"retry-after": _retry} if _retry else {})}), content)

        def _gspread(_status):
            response = requests.Response()
            response.status_code = _status
            response._content = json.dumps({"error": {"code": _status, "message": "m", "status": "s"}}).encode()
            return gspread.exceptions.APIError(response)

        for label, failed, exception, expected in [
            ("google rate limit", google_failed, _google(429, _retry="7"), (429, "7")),
            ("google user rate limit as 403", google_failed, _google(403, "userRateLimitExceeded"), (429, None)),
            ("google forbidden", google_failed, _google(403, "forbidden"), (403, None)),
            ("google backend", google_failed, _google(503, "backendError"), (503, None)),
            ("gspread rate limit", google_failed, _gspread(429), (429, None)),
            ("google transport", google_failed, TimeoutError("timed out"), (503, None)),
            ("google other", google_failed, ValueError("bad"), None),
            ("yahoo rate limit", yahoo_failed, yfinance.exceptions.YFRateLimitError(), (429, None)),
            ("yahoo other", yahoo_failed, ValueError("bad"), None),
        ]:
            failure = failed(exception)
            self.assertEqual(expected, None if failure is None else (failure[0], failure[1].get("Retry-After") if failure[1] is not None else None), label)

    def test_library_drive_throttled(self):
        waits = []
        mock.patch("wrangle.plugin._throttle.time.sleep", waits.append).start()
        test = PluginStub("Test", "folder")
        test.throttles = {"google_drive": Throttle("google_drive", plugin.GOOGLE_DRIVE_BACKOFF, test.print_log)}
        plugin.config.repo_scope = plugin.RepoScope.RELEASE
        plugin.config.disable_drive_downloads = False
        drive = _FakeDrive()
        drive.put("a.csv", b"1")
        drive.failures = [googleapiclient.errors.HttpError(httplib2.Response({"status": 403}), json.dumps({"error": {"errors": [{"reason": "rateLimitExceeded"}]}}).encode())]
        drive.patch()
        self.assertEqual({"a.csv": "downloaded"}, {basename(path): str(status) for path, status in test.drive_synchronise("folder", test.local_cache, download=True).items()})
        self.assertEqual(([2], 2), ([round(wait) for wait in waits], drive.calls["list"]))

    def test_library_stock_throttled(self):
        waits, calls = [], []
        mock.patch("wrangle.plugin._throttle.time.sleep", waits.append).start()

        class _Ticker:
            def __init__(self, _ticker):
                pass

            def history(self, **_kwargs):
                calls.append(1)
                if len(calls) == 1:
                    raise yfinance.exceptions.YFRateLimitError()
                return pd.DataFrame({"Close": [1.0]}, index=pd.DatetimeIndex(["2026-01-05"]))

        mock.patch("wrangle.plugin._sources.yf.Ticker", _Ticker).start()
        plugin.config.disable_source_downloads = False
        plugin.config.clock = datetime.datetime.fromisoformat("2026-02-01T12:00:00")
        test = PluginStub("Test", "SOME_NON_EXISTANT_GUID")
        test.throttles = {"yahoo": Throttle("yahoo", plugin.YAHOO_BACKOFF, test.print_log)}
        local_path = join(test.local_cache, "yahoo_test_2026-01.csv")
        self.assertEqual(DownloadStatus.DOWNLOADED, test.stock_download(local_path, "TEST", "2026-01-01", "2026-01-31", check=False).file_status)
        self.assertEqual(([5], 2), ([round(wait) for wait in waits], len(calls)))

    def test_library_redbark_throttled(self):
        requested = []

        def _urlopen(request, *_args, **_kwargs):
            requested.append(request.full_url)
            if len(requested) == 1:
                raise urllib.error.HTTPError(request.full_url, 429, "offline fixture error", Message(), None)
            return urllib.response.addinfourl(io.BytesIO(json.dumps({"data": [{"id": "r1"}], "pagination": {"hasMore": False}}).encode()), Message(), request.full_url, 200)

        mock.patch("wrangle.plugin._sources.urllib.request.urlopen", _urlopen).start()
        mock.patch("wrangle.plugin._throttle.time.sleep", lambda _seconds: None).start()
        plugin.config.disable_source_downloads = False
        local_path = join(DIR_ROOT, "target", "data", "_redbark_things.csv")
        unregistered = PluginStub("Test", "SOME_NON_EXISTANT_GUID")
        self.assertEqual(([429], 1), ([error["Status"] for error in unregistered.redbark_download(["/v1/things"], local_path, ["id"], ignore=True).errors], len(requested)))
        requested.clear()
        registered = PluginStub("Test", "SOME_NON_EXISTANT_GUID")
        registered.throttles = {"redbark": Throttle("redbark", plugin.REDBARK_BACKOFF, registered.print_log)}
        self.assertEqual((DownloadStatus.DOWNLOADED, 2), (registered.redbark_download(["/v1/things"], local_path, ["id"]).file_status, len(requested)))

    def test_library_database(self):
        test = PluginStub("Test", "SOME_NON_EXISTANT_GUID")
        reset_config()
        csv_path = abspath(f"{test.local_cache}/_database_test.csv")

        invalid_cache = "Invalid"
        invalid_path = abspath(f"{test.local_cache}/_database_{invalid_cache.lower()}.csv")
        for result in [
            test.database_download(invalid_cache, "SELECT 1"),
            test.database_download(invalid_cache, "SELECT 1", check=False),
        ]:
            self.assertEqual(DownloadResult(DownloadStatus.FAILED, []), result)
        self.assertFalse(isfile(invalid_path))

        cache_cache = "Cache"
        cache_path = abspath(f"{test.local_cache}/_database_{cache_cache.lower()}.csv")
        with open(cache_path, "w") as fh:
            fh.write("time,entity,type,period,unit,value\n2020-01-01,AUD/USD,snapshot,1d,$,0.65\n")
        self.assertEqual(DownloadResult(DownloadStatus.CACHED, [cache_path]), test.database_download(cache_cache, "SELECT 1"))
        plugin.config.disable_source_downloads = True
        self.assertEqual(DownloadResult(DownloadStatus.CACHED, [cache_path]), test.database_download(cache_cache, "SELECT 1"))
        reset_config()

        test.reset_counters()
        test.database_upload(test.dataframe_new())
        test.database_upload(pl.DataFrame({"Date": pl.Series([], dtype=pl.Date)}))
        self.assertFalse(csv_path in test._db_cache_dfs)
        self.assertEqual(0, test.get_counter(plugin.CTR_SRC_EGRESS, plugin.CTR_ACT_DATABASE_ROWS))
        self.assertEqual(0, test.get_counter(plugin.CTR_SRC_EGRESS, plugin.CTR_ACT_DATABASE_COLUMNS))

        test.reset_counters()
        equity_df = pl.DataFrame(
            {
                "Date": pl.Series([date_type(2024, 1, 1), date_type(2024, 1, 2), date_type(2024, 1, 3)], dtype=pl.Date),
                "AORD Price Close": [729.0, 726.5, 721.4],
            }
        )
        test.database_upload(equity_df, metric_type="price-close", period="1d", unit="$")
        long_df = test._db_cache_dfs[csv_path]
        self.assertEqual(["time", "entity", "type", "period", "unit", "value"], long_df.columns)
        self.assertEqual(3, len(long_df))
        self.assertEqual(["AORD"], long_df["entity"].unique().to_list())
        self.assertEqual(["price-close"], long_df["type"].unique().to_list())
        self.assertEqual(["1d"], long_df["period"].unique().to_list())
        self.assertEqual(["$"], long_df["unit"].unique().to_list())
        self.assertEqual([729.0, 726.5, 721.4], long_df.sort("time")["value"].to_list())
        self.assertEqual(1, test.get_counter(plugin.CTR_SRC_EGRESS, plugin.CTR_ACT_DATABASE_COLUMNS))
        self.assertEqual(3, test.get_counter(plugin.CTR_SRC_EGRESS, plugin.CTR_ACT_DATABASE_ROWS))

        test.reset_counters()
        test._db_cache_dfs.clear()
        currency_df = pl.DataFrame(
            {
                "Date": pl.Series([date_type(2024, 1, 1), date_type(2024, 1, 2)], dtype=pl.Date),
                "AUD/USD": [0.65, 0.66],
                "AUD/GBP": [0.50, 0.51],
                "AUD/SGD": [0.90, 0.91],
            }
        )
        test.database_upload(currency_df, metric_type="snapshot", period="1d", unit="$")
        long_df = test._db_cache_dfs[csv_path]
        self.assertEqual(6, len(long_df))
        self.assertEqual({"AUD/USD", "AUD/GBP", "AUD/SGD"}, set(long_df["entity"].to_list()))
        self.assertEqual({"snapshot"}, set(long_df["type"].to_list()))
        self.assertEqual(3, test.get_counter(plugin.CTR_SRC_EGRESS, plugin.CTR_ACT_DATABASE_COLUMNS))
        self.assertEqual(2, test.get_counter(plugin.CTR_SRC_EGRESS, plugin.CTR_ACT_DATABASE_ROWS))

        test.reset_counters()
        test._db_cache_dfs.clear()
        sparse_df = pl.DataFrame(
            {
                "Date": pl.Series([date_type(2024, 2, 1), date_type(2024, 2, 2), date_type(2024, 2, 3)], dtype=pl.Date),
                "AXJO Price Close": [5000.0, None, 5100.0],
            }
        )
        test.database_upload(sparse_df, metric_type="price-close", period="1d", unit="$")
        long_df = test._db_cache_dfs[csv_path]
        self.assertEqual(2, len(long_df))
        self.assertNotIn(None, long_df["value"].to_list())
        self.assertEqual(3, test.get_counter(plugin.CTR_SRC_EGRESS, plugin.CTR_ACT_DATABASE_ROWS))

        test.reset_counters()
        test._db_cache_dfs.clear()
        call1 = pl.DataFrame(
            {
                "Date": pl.Series([date_type(2024, 3, 1), date_type(2024, 3, 2)], dtype=pl.Date),
                "AUD/USD": [0.65, 0.66],
            }
        )
        call2 = pl.DataFrame(
            {
                "Date": pl.Series([date_type(2024, 3, 2), date_type(2024, 3, 3)], dtype=pl.Date),
                "AUD/USD": [0.67, 0.68],
            }
        )
        test.database_upload(call1, metric_type="snapshot", period="1d", unit="$")
        test.database_upload(call2, metric_type="snapshot", period="1d", unit="$")
        long_df = test._db_cache_dfs[csv_path]
        self.assertEqual(3, len(long_df))
        mar2 = long_df.filter(pl.col("time") == date_type(2024, 3, 2))
        self.assertEqual(1, len(mar2))
        self.assertEqual(0.67, mar2["value"][0])

        test.reset_counters()
        test._db_cache_dfs.clear()
        snapshot_df = pl.DataFrame(
            {
                "Date": pl.Series([date_type(2024, 4, 1)], dtype=pl.Date),
                "AUD/USD": [0.65],
            }
        )
        delta_df = pl.DataFrame(
            {
                "Date": pl.Series([date_type(2024, 4, 1)], dtype=pl.Date),
                "AUD/USD": [-1.53],
            }
        )
        test.database_upload(snapshot_df, metric_type="snapshot", period="1d", unit="$")
        test.database_upload(delta_df, metric_type="delta", period="1d", unit="%")
        long_df = test._db_cache_dfs[csv_path]
        self.assertEqual(2, len(long_df))
        self.assertEqual({"snapshot", "delta"}, set(long_df["type"].to_list()))
        self.assertEqual({"$", "%"}, set(long_df["unit"].to_list()))

    def test_database_schema_generated(self):
        reset_config()
        schemas_dir = abspath(join(dirname(realpath(__file__)), "../../../../src/build/resources/schema/postgres"))
        image_dir = abspath(join(dirname(realpath(__file__)), "../../../../src/main/resources/image/database"))
        for artifact in ("describe.sh", "query.sh", "verify.sh"):
            self.assertTrue(isfile(join(schemas_dir, artifact)), f"missing generated artifact [{artifact}]")
        for runner in ("describe", "verify"):
            script = Path(join(schemas_dir, f"{runner}.sh")).read_text()
            self.assertIn(f"{runner}_sql() {{", script, f"[{runner}.sh] does not carry its SQL inline")
        self.assertNotIn("SCHEMA_SQL", Path(join(schemas_dir, "query.sh")).read_text())
        self.assertEqual([], sorted(Path(join(schemas_dir, "query")).glob("query_*.sql")))
        for plugin_name in wrangle_main._get_plugins():
            instance = wrangle_main._instantiate_plugin(plugin_name)
            if not instance.database:
                continue
            table_sql = join(schemas_dir, "model", f"{plugin_name}.sql")
            query_sql = join(schemas_dir, "query", f"{plugin_name}.sql")
            self.assertTrue(isfile(table_sql), f"missing generated DDL for table [{plugin_name}]")
            self.assertTrue(isfile(query_sql), f"missing generated queries for table [{plugin_name}]")
            ddl = Path(table_sql).read_text()
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {plugin_name} (", ddl)
            self.assertIn("PRIMARY KEY (time, entity, type, period, unit)", ddl)
            self.assertIn(f"SELECT create_hypertable('{plugin_name}', 'time'", ddl)
            self.assertEqual(ddl, Path(join(image_dir, f"{plugin_name}.sql")).read_text())
            self.assertEqual(join(image_dir, f"{plugin_name}.sql"), database.database_schema_path(plugin_name))

    def test_library_dataframe(self):
        test = PluginStub("Test", "SOME_NON_EXISTANT_GUID")

        df_empty_str = "[{}]"
        df_empty_type = {"C1": pl.Int16}
        self.assertEqual(df_empty_str.format(""), test.dataframe_to_str(test.dataframe_new()))
        self.assertEqual(df_empty_str.format(""), test.dataframe_to_str(test.dataframe_new([])))
        self.assertEqual(df_empty_str.format(""), test.dataframe_to_str(test.dataframe_new([], {})))
        self.assertEqual(df_empty_str.format("C1(Int16)"), test.dataframe_to_str(test.dataframe_new([], df_empty_type)))

        df_data_str = "[C1({}), C2({}), C3({})]"
        df_data_type = {
            "C1": pl.Int64,
            "C2": pl.Utf8,
            "C3": pl.Utf8,
        }
        df_data = [{"C1": 1, "C2": 1.1, "C3": "1"}, {"C1": 2, "C2": 2.2, "C3": "2"}, {"C1": None, "C2": None, "C3": None}]
        self.assertEqual(df_data_str.format("Int64", "Float64", "String"), test.dataframe_to_str(test.dataframe_new(df_data)))
        self.assertEqual(df_data_str.format("Int64", "Float64", "String"), test.dataframe_to_str(test.dataframe_new(df_data, {})))
        self.assertEqual(df_data_str.format("Int64", "String", "String"), test.dataframe_to_str(test.dataframe_new(df_data, df_data_type)))
        self.assertEqual(3, len(test.dataframe_new(df_data, schema=dict.fromkeys(df_data[0], pl.Utf8))))

        df_lots_cols = 50
        df_lots_rows = 100
        df_lots = [{f"C{c}": v * v / 0.2 for c in range(1, df_lots_cols + 1)} for v in range(1, df_lots_rows + 1)]
        self.assertEqual(True, isinstance(test.dataframe_to_str(test.dataframe_new(df_lots, print_label="lots")), str))
        self.assertEqual(True, isinstance(test.dataframe_to_str(test.dataframe_new(schema=df_data_type, print_label="lots")), str))
        self.assertEqual(False, isinstance(test.dataframe_to_str(test.dataframe_new(df_lots, print_label="lots")), list))
        self.assertEqual(True, isinstance(test.dataframe_to_str(test.dataframe_new(df_lots, print_label="lots"), False), list))
        self.assertEqual(df_lots_rows + 6, len(test.dataframe_to_str(test.dataframe_new(df_lots, print_label="lots"), False, -1)))
        self.assertEqual(df_lots_rows + 6, len(test.dataframe_to_str(test.dataframe_new(df_lots, print_label="lots"), False, 100)))
        self.assertEqual(5 + 7, len(test.dataframe_to_str(test.dataframe_new(df_lots, print_label="lots"), False, 5)))
        self.assertEqual(0 + 7, len(test.dataframe_to_str(test.dataframe_new(df_lots, print_label="lots"), False, 0)))
        self.assertEqual(df_lots_rows, len(test.dataframe_new(df_lots)))
        self.assertEqual(df_lots_rows, len(test.dataframe_new(df_lots, schema={"SOME UNKNOWN COLUMN": pl.Utf8})))
        self.assertEqual(df_lots_rows, len(test.dataframe_new(df_lots, schema=dict.fromkeys(df_data[0], pl.Utf8))))
        self.assertEqual(df_lots_rows, len(test.dataframe_new(df_lots, schema=dict.fromkeys(df_lots[0], pl.Utf8))))

    def test_library_stock(self):
        test = PluginStub("Test", "SOME_NON_EXISTANT_GUID")
        plugin.config.disable_source_downloads = False
        plugin.config.force_downloads = False

        def _history(dates):
            index = pd.DatetimeIndex([pd.Timestamp(stock_date) for stock_date in dates]).tz_localize("Australia/Sydney")
            return pd.DataFrame(
                {
                    "Open": 1.0,
                    "High": 1.0,
                    "Low": 1.0,
                    "Close": 1.0,
                    "Volume": 1,
                    "Dividends": 0.0,
                    "Stock Splits": 0.0,
                },
                index=index,
            )

        with tempfile.TemporaryDirectory() as cache_dir, mock.patch("wrangle.plugin._sources.yf.Ticker") as ticker:
            ticker.return_value.history.return_value = _history(["2025-09-30"])
            result = test.stock_download(join(cache_dir, "yahoo_aord_2025-10.csv"), "^AORD", "2025-10-01", "2025-10-31", check=False)
            self.assertEqual(DownloadStatus.SKIPPED, result.file_status)
            self.assertFalse(isfile(join(cache_dir, "yahoo_aord_2025-10.csv")))

            ticker.return_value.history.return_value = _history(["2025-08-29", "2025-09-01", "2025-09-30", "2025-10-01"])
            result = test.stock_download(join(cache_dir, "yahoo_aord_2025-09.csv"), "^AORD", "2025-09-01", "2025-09-30", check=False)
            self.assertEqual(DownloadStatus.DOWNLOADED, result.file_status)
            self.assertEqual(["2025-09-01", "2025-09-30"], pl.read_csv(join(cache_dir, "yahoo_aord_2025-09.csv")).get_column("Date").to_list())

    ########################################################################################################################
    # State
    ########################################################################################################################

    def test_state_cache_first_run(self):
        t = self._setup_state_test("test-1")
        update = self._df([("2020-01-01", 1.0), ("2020-02-01", 2.0)])
        delta, current, previous = t.state_cache(update)
        self.assertEqual(2, len(delta))
        self.assertEqual(2, len(current))
        self.assertEqual(0, len(previous))

    def test_state_cache_append_rows(self):
        t = self._setup_state_test("test-2")
        update = self._df([("2020-01-01", 1.0), ("2020-02-01", 2.0), ("2020-03-01", 3.0)])
        delta, current, previous = t.state_cache(update)
        self.assertEqual(1, len(delta))
        self.assertEqual("2020-03-01", str(delta.sort("Date")["Date"][0]))
        self.assertEqual(3.0, delta.sort("Date")["Value"][0])
        self.assertEqual(3, len(current))
        self.assertEqual(2, len(previous))

    def test_state_cache_changed_values(self):
        t = self._setup_state_test("test-3")
        update = self._df([("2020-01-01", 1.0), ("2020-02-01", 2.5)])
        delta, _current, _previous = t.state_cache(update)
        self.assertEqual(1, len(delta))
        self.assertEqual(2.5, delta["Value"][0])

    def test_state_cache_new_column(self):
        t = self._setup_state_test("test-4")
        update = pl.DataFrame(
            {
                "Date": ["2020-01-01", "2020-02-01"],
                "Value": [1.0, 2.0],
                "Extra": [10.0, 20.0],
            }
        ).with_columns(pl.col("Date").str.to_date())
        delta, current, previous = t.state_cache(update)
        self.assertIn("Extra", current.columns)
        self.assertIn("Extra", previous.columns)
        self.assertIsNone(previous.sort("Date")["Extra"][0])
        self.assertEqual(2, len(current))
        self.assertEqual([10.0, 20.0], current.sort("Date")["Extra"].to_list())
        self.assertGreater(len(delta), 0)
        self.assertEqual(10.0, delta.sort("Date")["Extra"][0])

    def test_state_cache_empty_update(self):
        t = self._setup_state_test("test-5")
        update = pl.DataFrame(schema={"Date": pl.Date, "Value": pl.Float64})
        delta, current, previous = t.state_cache(update)
        self.assertEqual(0, len(delta))
        self.assertEqual(3, len(current))
        self.assertEqual(3, len(previous))

    def test_state_cache_idempotent(self):
        t = self._setup_state_test("test-2")
        update = self._df([("2020-01-01", 1.0), ("2020-02-01", 2.0)])
        t.state_cache(update)
        t.reset_counters()
        delta, current, _ = t.state_cache(update)
        self.assertEqual(0, len(delta))
        self.assertEqual(2, len(current))

    def test_state_cache_with_aggregate(self):
        t = self._setup_state_test("test-1")
        update = self._df([("2020-01-01", 10.0), ("2020-02-01", 20.0), ("2020-03-01", 30.0)])
        delta, current, _ = t.state_cache(update, lambda df: df.with_columns((pl.col("Value") * 2).alias("Double")))
        self.assertIn("Double", current.columns)
        self.assertEqual([20.0, 40.0, 60.0], current.sort("Date")["Double"].to_list())
        self.assertEqual(3, len(delta))

    def test_state_cache_no_new_rows(self):
        t = self._setup_state_test("test-2")
        update = self._df([("2020-01-01", 1.0), ("2020-02-01", 2.0)])
        delta, current, previous = t.state_cache(update)
        self.assertEqual(0, len(delta))
        self.assertEqual(2, len(current))
        self.assertEqual(2, len(previous))

    def test_state_cache_subset_rows(self):
        t = self._setup_state_test("test-5")
        update = self._df([("2020-01-01", 1.0)])
        delta, current, _ = t.state_cache(update)
        self.assertEqual(0, len(delta))
        self.assertEqual(3, len(current))
        dates = [str(d) for d in current.sort("Date")["Date"].to_list()]
        self.assertEqual(["2020-01-01", "2020-02-01", "2020-03-01"], dates)

    def test_state_cache_deleted_column(self):
        t = self._setup_state_test("test-6")
        update = self._df([("2020-01-01", 1.0), ("2020-02-01", 2.0)])
        delta, current, previous = t.state_cache(update)
        self.assertIn("Extra", current.columns)
        self.assertIsNone(current.sort("Date")["Extra"][0])
        self.assertEqual(10.0, previous.sort("Date")["Extra"][0])
        self.assertEqual(2, len(delta))
        self.assertIsNone(delta.sort("Date")["Extra"][0])

    def test_state_cache_force_reload(self):
        t = self._setup_state_test("test-2")
        plugin.config.force_reprocessing = True
        update = self._df([("2020-01-01", 1.0), ("2020-02-01", 2.0), ("2020-03-01", 3.0)])
        delta, current, previous = t.state_cache(update)
        self.assertEqual(3, len(delta))
        self.assertEqual(3, len(current))
        self.assertEqual(0, len(previous))

    def test_state_cache_invalid_schema(self):
        t = self._setup_state_test("test-1")
        with self.assertRaises(pl.exceptions.SchemaError):
            t.state_cache(pl.DataFrame({"NotDate": ["x"], "Value": [1.0]}))
        with self.assertRaises(pl.exceptions.SchemaError):
            t.state_cache(pl.DataFrame({"Date": ["2020-01-01"], "Value": [1.0]}))
        with self.assertRaises(pl.exceptions.SchemaError):
            t.state_cache(pl.DataFrame())

    def test_state_cache_orphaned_previous(self):
        t = self._setup_state_test("test-7")
        update = self._df([("2020-01-01", 1.0), ("2020-02-01", 2.0)])
        delta, current, previous = t.state_cache(update)
        self.assertEqual(2, len(delta))
        self.assertEqual(2, len(current))
        self.assertEqual(0, len(previous))

    def test_state_cache_duplicate_dates_in_update(self):
        t = self._setup_state_test("test-1")
        update = pl.DataFrame(
            {
                "Date": ["2020-01-01", "2020-01-01", "2020-02-01"],
                "Value": [1.0, 9.9, 2.0],
            }
        ).with_columns(pl.col("Date").str.to_date())
        delta, current, _ = t.state_cache(update)
        self.assertEqual(2, len(current))
        self.assertEqual(9.9, current.sort("Date")["Value"][0])
        self.assertEqual(2, len(delta))

    def test_state_cache_no_overlap_with_current(self):
        t = self._setup_state_test("test-2")
        update = self._df([("2020-03-01", 3.0), ("2020-04-01", 4.0)])
        delta, current, _ = t.state_cache(update)
        self.assertEqual(2, len(delta))
        self.assertEqual(4, len(current))
        self.assertEqual(["2020-01-01", "2020-02-01", "2020-03-01", "2020-04-01"], [str(d) for d in current.sort("Date")["Date"].to_list()])

    def test_state_cache_mixed_delta(self):
        t = self._setup_state_test("test-5")
        update = self._df([("2020-01-01", 1.0), ("2020-02-01", 2.5), ("2020-04-01", 4.0)])
        delta, current, _ = t.state_cache(update)
        self.assertEqual(4, len(current))
        delta_dates = sorted([str(d) for d in delta["Date"].to_list()])
        self.assertEqual(["2020-02-01", "2020-04-01"], delta_dates)
        feb = delta.filter(pl.col("Date") == pl.lit("2020-02-01").str.to_date())["Value"][0]
        self.assertEqual(2.5, feb)

    def test_state_cache_multiple_columns_changed(self):
        t = self._setup_state_test("test-6")
        update = pl.DataFrame(
            {
                "Date": ["2020-01-01", "2020-02-01"],
                "Value": [9.0, 9.0],
                "Extra": [90.0, 90.0],
            }
        ).with_columns(pl.col("Date").str.to_date())
        delta, _current, _ = t.state_cache(update)
        self.assertEqual(2, len(delta))
        self.assertEqual(9.0, delta.sort("Date")["Value"][0])
        self.assertEqual(90.0, delta.sort("Date")["Extra"][0])

    def test_state_cache_previous_tracks_last_run(self):
        t = self._setup_state_test("test-1")
        _, _, prev1 = t.state_cache(self._df([("2020-01-01", 1.0)]))
        self.assertEqual(0, len(prev1))
        t.reset_counters()
        _, _, prev2 = t.state_cache(self._df([("2020-01-01", 1.0), ("2020-02-01", 2.0)]))
        self.assertEqual(1, len(prev2))
        self.assertEqual(1.0, prev2.sort("Date")["Value"][0])
        t.reset_counters()
        _, _, prev3 = t.state_cache(self._df([("2020-01-01", 9.0), ("2020-02-01", 2.0)]))
        self.assertEqual(2, len(prev3))
        self.assertEqual(1.0, prev3.sort("Date")["Value"][0])

    def test_state_cache_new_column_second_run(self):
        t = self._setup_state_test("test-1")
        t.state_cache(self._df([("2020-01-01", 1.0), ("2020-02-01", 2.0)]))
        t.reset_counters()
        run2 = pl.DataFrame(
            {
                "Date": ["2020-01-01", "2020-02-01"],
                "Value": [1.0, 2.0],
                "Extra": [10.0, 20.0],
            }
        ).with_columns(pl.col("Date").str.to_date())
        delta, current, previous = t.state_cache(run2)
        self.assertIn("Extra", current.columns)
        self.assertEqual([10.0, 20.0], current.sort("Date")["Extra"].to_list())
        self.assertIn("Extra", previous.columns)
        self.assertIsNone(previous.sort("Date")["Extra"][0])
        self.assertEqual(2, len(delta))
        self.assertEqual(10.0, delta.sort("Date")["Extra"][0])

    def test_state_cache_counter_delta_columns(self):
        t = self._setup_state_test("test-6")
        t.state_cache(self._df([("2020-01-01", 9.0), ("2020-02-01", 9.0)]))
        self.assertEqual(2, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_DELTA_COLUMNS))

    def test_state_cache_aggregate_called_twice(self):
        t = self._setup_state_test("test-2")
        calls = 0

        def counting(df):
            nonlocal calls
            calls += 1
            return df

        t.state_cache(self._df([("2020-03-01", 3.0)]), counting)
        self.assertEqual(2, calls)

    def test_state_cache_null_date_in_update(self):
        t = self._setup_state_test("test-1")
        update = pl.DataFrame(
            {
                "Date": [None, "2020-01-01", "2020-02-01"],
                "Value": [99.0, 1.0, 2.0],
            }
        ).with_columns(pl.col("Date").str.to_date(strict=False))
        delta, current, _ = t.state_cache(update)
        dates = [str(d) for d in current.sort("Date")["Date"].to_list()]
        self.assertNotIn("None", dates)
        self.assertEqual(["2020-01-01", "2020-02-01"], dates)
        self.assertEqual(2, len(current))
        self.assertEqual(2, len(delta))
        delta_dates = [str(d) for d in delta["Date"].to_list()]
        self.assertNotIn("None", delta_dates)
        self.assertIsNotNone(current.sort("Date")["Date"][0])

    def test_state_cache_previous_columns_reflects_union_schema(self):
        t = self._setup_state_test("test-4")
        update = pl.DataFrame(
            {
                "Date": ["2020-01-01", "2020-02-01"],
                "Value": [1.0, 2.0],
                "Extra": [10.0, 20.0],
                "Third": [100.0, 200.0],
            }
        ).with_columns(pl.col("Date").str.to_date())
        t.state_cache(update)
        self.assertEqual(3, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_PREVIOUS_COLUMNS))

    def _price_df(self, date_price_pairs, ticker="AAPL"):
        return pl.DataFrame(
            {
                "Date": [p[0] for p in date_price_pairs],
                f"{ticker} Price Close": [float(p[1]) for p in date_price_pairs],
            }
        ).with_columns(pl.col("Date").str.to_date())

    def _price_change_agg(self, ticker="AAPL"):
        price_col = f"{ticker} Price Close"
        change_col = f"{ticker} Price Close 1d-Change Percentage"

        def _agg(df):
            str_cols = [c for c, t in zip(df.columns, df.dtypes, strict=False) if _is_string_col(c, t)]
            if str_cols:
                df = df.with_columns([pl.col(c).cast(pl.Float64, strict=False) for c in str_cols])
            if price_col in df.columns:
                df = df.with_columns(pl.when(pl.col(price_col).is_null()).then(None).otherwise(pl.col(price_col).pct_change(1).fill_nan(None) * 100).alias(change_col))
                df = df.with_columns(pl.when(pl.col(price_col).is_not_null() & pl.col(change_col).is_null()).then(pl.lit(0.0)).otherwise(pl.col(change_col)).alias(change_col))
            out_cols = [c for c in ["Date", price_col, change_col] if c in df.columns]
            out = df.select(out_cols)
            return out.with_columns(pl.col(change_col).round(4)) if change_col in out.columns else out

        return _agg

    def test_state_cache_aggregate_derived_columns(self):
        t = self._setup_state_test("agg-1")
        data = self._price_df(
            [
                ("2020-01-01", 100.0),
                ("2020-02-01", 200.0),
                ("2020-03-01", 300.0),
            ]
        )
        delta, current, previous = t.state_cache(data, self._price_change_agg())
        self.assertEqual(3, len(delta))
        self.assertEqual(3, len(current))
        self.assertEqual(0, len(previous))
        self.assertIn("AAPL Price Close 1d-Change Percentage", current.columns)
        self.assertNotIn("AAPL Price Close 1d-Change Percentage", data.columns)
        changes = current.sort("Date")["AAPL Price Close 1d-Change Percentage"].to_list()
        self.assertEqual(0.0, changes[0])
        self.assertEqual(100.0, changes[1])
        self.assertEqual(50.0, changes[2])

    def test_state_cache_aggregate_idempotent(self):
        t = self._setup_state_test("agg-2")
        data = self._price_df(
            [
                ("2020-01-01", 100.0),
                ("2020-02-01", 200.0),
                ("2020-03-01", 300.0),
            ]
        )
        t.state_cache(data, self._price_change_agg())
        t.reset_counters()
        delta, current, _ = t.state_cache(data, self._price_change_agg())
        self.assertEqual(0, len(delta))
        self.assertEqual(3, len(current))
        self.assertEqual(0, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_DELTA_ROWS))
        self.assertEqual(3, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_CURRENT_ROWS))

    def test_state_cache_aggregate_cross_boundary(self):
        t = self._setup_state_test("agg-3")
        t.state_cache(
            self._price_df(
                [
                    ("2020-01-01", 100.0),
                    ("2020-02-01", 200.0),
                    ("2020-03-01", 300.0),
                ]
            ),
            self._price_change_agg(),
        )
        t.reset_counters()
        delta, current, _ = t.state_cache(
            self._price_df(
                [
                    ("2020-01-01", 100.0),
                    ("2020-02-01", 200.0),
                    ("2020-03-01", 300.0),
                    ("2020-04-01", 400.0),
                    ("2020-05-01", 600.0),
                ]
            ),
            self._price_change_agg(),
        )
        self.assertEqual(2, len(delta))
        self.assertEqual(5, len(current))
        delta_sorted = delta.sort("Date")
        self.assertEqual(33.3333, delta_sorted["AAPL Price Close 1d-Change Percentage"][0])
        self.assertEqual(50.0, delta_sorted["AAPL Price Close 1d-Change Percentage"][1])

    def test_state_cache_aggregate_narrows_columns(self):
        t = self._setup_state_test("agg-4")
        data = pl.DataFrame(
            {
                "Date": ["2020-01-01", "2020-02-01"],
                "AAPL Price Close": [100.0, 200.0],
                "AAPL Market Volume": [1000.0, 2000.0],
                "AAPL Currency Base": ["AUD", "AUD"],
            }
        ).with_columns(pl.col("Date").str.to_date())
        delta, current, _ = t.state_cache(data, self._price_change_agg())
        self.assertNotIn("AAPL Market Volume", current.columns)
        self.assertNotIn("AAPL Currency Base", current.columns)
        self.assertIn("AAPL Price Close", current.columns)
        self.assertIn("AAPL Price Close 1d-Change Percentage", current.columns)
        self.assertNotIn("AAPL Market Volume", delta.columns)

    def test_state_cache_null_column_csv_roundtrip(self):
        t = self._setup_state_test("agg-5")

        def agg_with_null_col(df):
            str_cols = [_c for _c, _t in zip(df.columns, df.dtypes, strict=False) if _is_string_col(_c, _t)]
            if str_cols:
                df = df.with_columns([pl.col(c).cast(pl.Float64, strict=False) for c in str_cols])
            return df.with_columns(pl.lit(None).cast(pl.Float64).alias("AAPL Baseline Price Close"))

        data = pl.DataFrame(
            {
                "Date": ["2020-01-01", "2020-02-01"],
                "AAPL Price Close": [100.0, 200.0],
            }
        ).with_columns(pl.col("Date").str.to_date())

        _, current1, _ = t.state_cache(data, agg_with_null_col)
        self.assertEqual(pl.Float64, current1["AAPL Baseline Price Close"].dtype)
        t.reset_counters()
        delta2, current2, _ = t.state_cache(data, agg_with_null_col)
        self.assertEqual(0, len(delta2))
        self.assertEqual(pl.Float64, current2["AAPL Baseline Price Close"].dtype)

    def test_state_cache_csv_files_written(self):
        t = self._setup_state_test("agg-6")
        t.state_cache(
            self._price_df(
                [
                    ("2020-01-01", 100.0),
                    ("2020-02-01", 200.0),
                ]
            ),
            self._price_change_agg(),
        )
        self.assertTrue(isfile(join(t.local_cache, "__test_current.csv")))
        self.assertTrue(isfile(join(t.local_cache, "__test_update.csv")))
        self.assertTrue(isfile(join(t.local_cache, "__test_delta.csv")))
        self.assertFalse(isfile(join(t.local_cache, "__test_previous.csv")))
        t.reset_counters()
        t.state_cache(
            self._price_df(
                [
                    ("2020-01-01", 100.0),
                    ("2020-02-01", 200.0),
                    ("2020-03-01", 300.0),
                    ("2020-04-01", 400.0),
                ]
            ),
            self._price_change_agg(),
        )
        self.assertTrue(isfile(join(t.local_cache, "__test_previous.csv")))
        self.assertEqual(4, len(t.csv_read(join(t.local_cache, "__test_current.csv"))))
        self.assertEqual(2, len(t.csv_read(join(t.local_cache, "__test_previous.csv"))))
        self.assertEqual(4, len(t.csv_read(join(t.local_cache, "__test_update.csv"))))
        self.assertEqual(2, len(t.csv_read(join(t.local_cache, "__test_delta.csv"))))

    def test_state_cache_row_and_column_counters(self):
        t = self._setup_state_test("agg-7")
        t.state_cache(
            self._price_df(
                [
                    ("2020-01-01", 100.0),
                    ("2020-02-01", 200.0),
                    ("2020-03-01", 300.0),
                ]
            ),
            self._price_change_agg(),
        )
        self.assertEqual(3, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_CURRENT_ROWS))
        self.assertEqual(3, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_UPDATE_ROWS))
        self.assertEqual(3, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_DELTA_ROWS))
        self.assertEqual(0, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_PREVIOUS_ROWS))
        self.assertEqual(2, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_CURRENT_COLUMNS))
        t.reset_counters()
        t.state_cache(
            self._price_df(
                [
                    ("2020-01-01", 100.0),
                    ("2020-02-01", 200.0),
                    ("2020-03-01", 300.0),
                    ("2020-04-01", 400.0),
                ]
            ),
            self._price_change_agg(),
        )
        self.assertEqual(4, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_CURRENT_ROWS))
        self.assertEqual(4, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_UPDATE_ROWS))
        self.assertEqual(1, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_DELTA_ROWS))
        self.assertEqual(3, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_PREVIOUS_ROWS))

    def test_state_cache_aggregate_with_guard(self):
        def null_fill_agg(df):
            str_cols = [_c for _c, _t in zip(df.columns, df.dtypes, strict=False) if _is_string_col(_c, _t)]
            if str_cols:
                df = df.with_columns([pl.col(c).cast(pl.Float64, strict=False) for c in str_cols])
            if "AAPL Price Close" in df.columns:
                if "AAPL Derived" not in df.columns:
                    df = df.with_columns(pl.lit(None).cast(pl.Float64).alias("AAPL Derived"))
                df = df.with_columns(pl.when(pl.col("AAPL Derived").is_null()).then(pl.col("AAPL Price Close") * 10.0).otherwise(pl.col("AAPL Derived")).alias("AAPL Derived"))
            out_cols = [c for c in ["Date", "AAPL Price Close", "AAPL Derived"] if c in df.columns]
            return df.select(out_cols)

        t = self._setup_state_test("agg-8")
        _, current1, _ = t.state_cache(self._price_df([("2020-01-01", 1.0), ("2020-02-01", 2.0)]), null_fill_agg)
        self.assertEqual([10.0, 20.0], current1.sort("Date")["AAPL Derived"].to_list())
        t.reset_counters()
        delta, current2, _ = t.state_cache(
            self._price_df([("2020-01-01", 1.0), ("2020-02-01", 2.0), ("2020-03-01", 3.0)]),
            null_fill_agg,
        )
        self.assertEqual(1, len(delta))
        sorted2 = current2.sort("Date")
        self.assertEqual(10.0, sorted2["AAPL Derived"][0])
        self.assertEqual(20.0, sorted2["AAPL Derived"][1])
        self.assertEqual(30.0, sorted2["AAPL Derived"][2])

    def test_state_cache_aggregate_nullfill_backfills_historical_rows(self):
        def null_fill_agg(df):
            str_cols = [_c for _c, _t in zip(df.columns, df.dtypes, strict=False) if _is_string_col(_c, _t)]
            if str_cols:
                df = df.with_columns([pl.col(c).cast(pl.Float64, strict=False) for c in str_cols])
            if "AAPL Price Close" in df.columns:
                if "AAPL Derived" not in df.columns:
                    df = df.with_columns(pl.lit(None).cast(pl.Float64).alias("AAPL Derived"))
                df = df.with_columns(pl.when(pl.col("AAPL Derived").is_null()).then(pl.col("AAPL Price Close") * 10.0).otherwise(pl.col("AAPL Derived")).alias("AAPL Derived"))
            out_cols = [c for c in ["Date", "AAPL Price Close", "AAPL Derived"] if c in df.columns]
            return df.select(out_cols)

        def seed_agg(df):
            if "AAPL Price Close" in df.columns:
                df = df.with_columns(pl.lit(None).cast(pl.Float64).alias("AAPL Derived"))
            out_cols = [c for c in ["Date", "AAPL Price Close", "AAPL Derived"] if c in df.columns]
            return df.select(out_cols)

        t = self._setup_state_test("agg-9")
        t.state_cache(self._price_df([("2020-01-01", 1.0), ("2020-02-01", 2.0)]), seed_agg)
        t.reset_counters()

        delta, current2, _ = t.state_cache(self._price_df([("2020-03-01", 3.0)]), null_fill_agg)
        self.assertEqual(3, len(current2))
        sorted2 = current2.sort("Date")
        self.assertEqual(10.0, sorted2["AAPL Derived"][0])
        self.assertEqual(20.0, sorted2["AAPL Derived"][1])
        self.assertEqual(30.0, sorted2["AAPL Derived"][2])
        self.assertEqual(3, len(delta))

    def _multi_key_dataframe(self, rows):
        return pl.DataFrame(
            {
                "Date": [r[0] for r in rows],
                "Account ID": [r[1] for r in rows],
                "Balance": [float(r[2]) for r in rows],
            }
        ).with_columns(pl.col("Date").str.to_date())

    def test_state_cache_multi_key_first_run(self):
        t = self._setup_state_test("mk-1")
        delta, current, previous = t.state_cache(self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]), key_columns=["Date", "Account ID"])
        self.assertEqual(2, len(delta))
        self.assertEqual(2, len(current))
        self.assertEqual(0, len(previous))

    def test_state_cache_multi_key_no_change(self):
        t = self._setup_state_test("mk-2")
        data = self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)])
        t.state_cache(data, key_columns=["Date", "Account ID"])
        t.reset_counters()
        delta, current, _ = t.state_cache(data, key_columns=["Date", "Account ID"])
        self.assertEqual(0, len(delta))
        self.assertEqual(2, len(current))

    def test_state_cache_multi_key_value_change(self):
        t = self._setup_state_test("mk-3")
        t.state_cache(self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]), key_columns=["Date", "Account ID"])
        t.reset_counters()
        delta, current, _ = t.state_cache(self._multi_key_dataframe([("2026-01-01", "acc-1", 150.0), ("2026-01-01", "acc-2", 200.0)]), key_columns=["Date", "Account ID"])
        self.assertEqual(1, len(delta))
        self.assertEqual(150.0, delta.filter(pl.col("Account ID") == "acc-1")["Balance"][0])
        self.assertEqual(2, len(current))

    def test_state_cache_multi_key_new_account(self):
        t = self._setup_state_test("mk-4")
        t.state_cache(self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0)]), key_columns=["Date", "Account ID"])
        t.reset_counters()
        delta, current, _ = t.state_cache(self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]), key_columns=["Date", "Account ID"])
        self.assertEqual(1, len(delta))
        self.assertEqual("acc-2", delta["Account ID"][0])
        self.assertEqual(2, len(current))

    def test_state_cache_multi_key_new_date(self):
        t = self._setup_state_test("mk-5")
        t.state_cache(self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]), key_columns=["Date", "Account ID"])
        t.reset_counters()
        delta, current, _ = t.state_cache(self._multi_key_dataframe([("2026-01-02", "acc-1", 110.0), ("2026-01-02", "acc-2", 210.0)]), key_columns=["Date", "Account ID"])
        self.assertEqual(2, len(delta))
        self.assertEqual(4, len(current))
        self.assertTrue(all(str(d) == "2026-01-02" for d in delta["Date"].to_list()))

    def test_state_cache_multi_key_partial_update(self):
        t = self._setup_state_test("mk-6")
        t.state_cache(
            self._multi_key_dataframe(
                [
                    ("2026-01-01", "acc-1", 100.0),
                    ("2026-01-01", "acc-2", 200.0),
                ]
            ),
            key_columns=["Date", "Account ID"],
        )
        t.reset_counters()
        delta, _current, _ = t.state_cache(
            self._multi_key_dataframe(
                [
                    ("2026-01-01", "acc-1", 150.0),
                    ("2026-01-01", "acc-2", 200.0),
                    ("2026-01-02", "acc-1", 155.0),
                ]
            ),
            key_columns=["Date", "Account ID"],
        )
        self.assertEqual(2, len(delta))
        delta_sorted = delta.sort(["Date", "Account ID"])
        self.assertEqual("2026-01-01", str(delta_sorted["Date"][0]))
        self.assertEqual("acc-1", delta_sorted["Account ID"][0])
        self.assertEqual("2026-01-02", str(delta_sorted["Date"][1]))

    def test_state_cache_multi_key_duplicate_keys_in_update(self):
        t = self._setup_state_test("mk-7")
        delta, current, _ = t.state_cache(
            self._multi_key_dataframe(
                [
                    ("2026-01-01", "acc-1", 100.0),
                    ("2026-01-01", "acc-1", 999.0),
                ]
            ),
            key_columns=["Date", "Account ID"],
        )
        self.assertEqual(1, len(current))
        self.assertEqual(999.0, current["Balance"][0])
        self.assertEqual(1, len(delta))

    def test_state_cache_multi_key_update_supersedes_current(self):
        t = self._setup_state_test("mk-8")
        t.state_cache(self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0)]), key_columns=["Date", "Account ID"])
        t.reset_counters()
        delta, current, previous = t.state_cache(self._multi_key_dataframe([("2026-01-01", "acc-1", 999.0)]), key_columns=["Date", "Account ID"])
        self.assertEqual(1, len(delta))
        self.assertEqual(999.0, current["Balance"][0])
        self.assertEqual(100.0, previous["Balance"][0])

    def test_state_cache_multi_key_counters(self):
        t = self._setup_state_test("mk-9")
        t.state_cache(self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0)]), key_columns=["Date", "Account ID"])
        self.assertEqual(1, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_UPDATE_COLUMNS))
        self.assertEqual(1, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_CURRENT_COLUMNS))
        self.assertEqual(1, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_DELTA_COLUMNS))

    def test_state_cache_multi_key_clean(self):
        t = self._setup_state_test("mk-10")
        t.state_cache(self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]), key_columns=["Date", "Account ID"])
        t.reset_counters()
        plugin.config.force_reprocessing = True
        delta, current, previous = t.state_cache(self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]), key_columns=["Date", "Account ID"])
        self.assertEqual(2, len(delta))
        self.assertEqual(2, len(current))
        self.assertEqual(0, len(previous))

    def test_state_cache_multi_key_with_aggregate(self):
        t = self._setup_state_test("mk-12")

        def _agg(df):
            if "Balance" in df.columns:
                df = df.with_columns((pl.col("Balance") * 2).alias("Balance Double"))
            return df

        _delta, current, _ = t.state_cache(self._multi_key_dataframe([("2026-01-01", "acc-1", 50.0), ("2026-01-01", "acc-2", 100.0)]), aggregate_func=_agg, key_columns=["Date", "Account ID"])
        self.assertIn("Balance Double", current.columns)
        doubles = current.sort(["Date", "Account ID"])["Balance Double"].to_list()
        self.assertEqual([100.0, 200.0], doubles)

    def test_state_cache_multi_key_null_date_dropped(self):
        t = self._setup_state_test("mk-13")
        data = pl.DataFrame(
            {
                "Date": [None, "2026-01-01"],
                "Account ID": ["acc-x", "acc-1"],
                "Balance": [999.0, 100.0],
            }
        ).with_columns(pl.col("Date").str.to_date(strict=False))
        _delta, current, _ = t.state_cache(data, key_columns=["Date", "Account ID"])
        self.assertEqual(1, len(current))
        self.assertEqual("acc-1", current["Account ID"][0])

    def test_state_cache_replace_partition(self):
        t = self._setup_state_test("mk-14")
        t.state_cache(
            self._multi_key_dataframe(
                [
                    ("2025-12-31", "acc-1", 10.0),
                    ("2026-01-01", "acc-1", 100.0),
                    ("2026-01-02", "acc-2", 200.0),
                    ("2026-01-03", "acc-3", 300.0),
                ]
            ),
            key_columns=["Date", "Account ID"],
        )
        t.reset_counters()
        delta, current, previous = t.state_cache(
            self._multi_key_dataframe(
                [
                    ("2026-01-01", "acc-1", 150.0),
                    ("2026-01-02", "acc-2", 200.0),
                    ("2026-01-04", "acc-4", 400.0),
                ]
            ),
            key_columns=["Date", "Account ID"],
            replace=pl.col("Date").dt.year() == 2026,
        )
        self.assertEqual(["acc-1", "acc-1", "acc-2", "acc-4"], current.sort("Date")["Account ID"].to_list())
        self.assertEqual([10.0, 150.0, 200.0, 400.0], current.sort("Date")["Balance"].to_list())
        self.assertEqual(["acc-1", "acc-4"], delta.sort("Date")["Account ID"].to_list())
        self.assertEqual(4, len(previous))
        deleted = pl.read_csv(join(t.local_cache, "__test_deleted.csv"))
        self.assertEqual(["acc-3"], deleted["Account ID"].to_list())

    def test_state_cache_replace_clears_values(self):
        t = self._setup_state_test("mk-15")
        t.state_cache(pl.DataFrame({"Date": ["2026-01-01"], "Account ID": ["acc-1"], "Category": ["Food"]}).with_columns(pl.col("Date").str.to_date()), key_columns=["Date", "Account ID"])
        t.reset_counters()
        delta, current, _ = t.state_cache(
            pl.DataFrame({"Date": ["2026-01-01"], "Account ID": ["acc-1"], "Category": [None]}, schema_overrides={"Category": pl.Utf8}).with_columns(pl.col("Date").str.to_date()),
            key_columns=["Date", "Account ID"],
            replace=pl.col("Date").dt.year() == 2026,
        )
        self.assertEqual([None], current["Category"].to_list())
        self.assertEqual(1, len(delta))

    def test_state_cache_removed_column_counter(self):
        t = self._setup_state_test("test-6")
        t.state_cache(self._df([("2020-01-01", 1.0), ("2020-02-01", 2.0)]))
        self.assertEqual(1, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_UPDATE_COLUMNS))
        self.assertEqual(2, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_PREVIOUS_COLUMNS))
        self.assertEqual(2, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_CURRENT_COLUMNS))

    def test_state_cache_multiple_new_columns(self):
        t = self._setup_state_test("test-2")
        update = pl.DataFrame(
            {
                "Date": ["2020-01-01", "2020-02-01"],
                "Value": [1.0, 2.0],
                "ColA": [10.0, 20.0],
                "ColB": [100.0, 200.0],
            }
        ).with_columns(pl.col("Date").str.to_date())
        delta, current, previous = t.state_cache(update)
        self.assertIn("ColA", current.columns)
        self.assertIn("ColB", current.columns)
        self.assertIsNone(previous.sort("Date")["ColA"][0])
        self.assertIsNone(previous.sort("Date")["ColB"][0])
        self.assertEqual([10.0, 20.0], current.sort("Date")["ColA"].to_list())
        self.assertEqual([100.0, 200.0], current.sort("Date")["ColB"].to_list())
        self.assertEqual(2, len(delta))

    def test_state_cache_multiple_removed_columns(self):
        t = self._setup_state_test("test-8")
        delta, current, previous = t.state_cache(self._df([("2020-01-01", 1.0), ("2020-02-01", 2.0)]))
        self.assertIn("Extra1", current.columns)
        self.assertIn("Extra2", current.columns)
        self.assertIsNone(current.sort("Date")["Extra1"][0])
        self.assertIsNone(current.sort("Date")["Extra2"][0])
        self.assertEqual(10.0, previous.sort("Date")["Extra1"][0])
        self.assertEqual(100.0, previous.sort("Date")["Extra2"][0])
        self.assertEqual(2, len(delta))
        self.assertEqual(1, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_UPDATE_COLUMNS))
        self.assertEqual(3, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_PREVIOUS_COLUMNS))

    def test_state_cache_multi_key_new_column(self):
        t = self._setup_state_test("mk-14")
        t.state_cache(self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]), key_columns=["Date", "Account ID"])
        t.reset_counters()
        update = pl.DataFrame(
            {
                "Date": ["2026-01-01", "2026-01-01"],
                "Account ID": ["acc-1", "acc-2"],
                "Balance": [100.0, 200.0],
                "Notes": ["note-a", "note-b"],
            }
        ).with_columns(pl.col("Date").str.to_date())
        delta, current, previous = t.state_cache(update, key_columns=["Date", "Account ID"])
        self.assertIn("Notes", current.columns)
        self.assertIn("Notes", previous.columns)
        self.assertIsNone(previous.sort(["Date", "Account ID"])["Notes"][0])
        self.assertEqual(["note-a", "note-b"], current.sort(["Date", "Account ID"])["Notes"].to_list())
        self.assertEqual(2, len(delta))

    def test_state_cache_multi_key_removed_column(self):
        t = self._setup_state_test("mk-15")
        initial = pl.DataFrame(
            {
                "Date": ["2026-01-01", "2026-01-01"],
                "Account ID": ["acc-1", "acc-2"],
                "Balance": [100.0, 200.0],
                "Notes": ["note-a", "note-b"],
            }
        ).with_columns(pl.col("Date").str.to_date())
        t.state_cache(initial, key_columns=["Date", "Account ID"])
        t.reset_counters()
        delta, current, previous = t.state_cache(self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]), key_columns=["Date", "Account ID"])
        self.assertIn("Notes", current.columns)
        self.assertIsNone(current.sort(["Date", "Account ID"])["Notes"][0])
        self.assertEqual("note-a", previous.sort(["Date", "Account ID"])["Notes"][0])
        self.assertEqual(2, len(delta))
        self.assertIsNone(delta.sort(["Date", "Account ID"])["Notes"][0])

    def test_state_cache_coalesce_preserves_current_when_update_null(self):
        t = self._setup_state_test("sc-1")
        first = pl.DataFrame(
            {
                "Date": ["2024-01-01", "2024-01-02"],
                "Value": [1.0, 2.0],
                "Extra": [10.0, 20.0],
            }
        ).with_columns(pl.col("Date").str.to_date())
        t.state_cache(first)
        t.reset_counters()
        update = pl.DataFrame(
            {
                "Date": ["2024-01-02", "2024-01-03"],
                "Value": [None, 3.0],
                "Extra": [None, 30.0],
            }
        ).with_columns(pl.col("Date").str.to_date())
        _, current, _ = t.state_cache(update)
        by_date = {row[0].isoformat(): (row[1], row[2]) for row in current.select(["Date", "Value", "Extra"]).rows()}
        self.assertEqual((1.0, 10.0), by_date["2024-01-01"])
        self.assertEqual((2.0, 20.0), by_date["2024-01-02"])
        self.assertEqual((3.0, 30.0), by_date["2024-01-03"])

    def _setup_state_test(self, fixture):
        t = PluginStub("Test", "SOME_NON_EXISTANT_GUID")
        t.local_cache = abspath(join(DIR_ROOT, "target", "data", f"state-{fixture}"))
        shutil.rmtree(t.local_cache, ignore_errors=True)
        os.makedirs(t.local_cache)
        src = join(DIR_ROOT, "src/test/resources/state", fixture, "data")
        if isdir(src):
            for fname in os.listdir(src):
                shutil.copy(join(src, fname), join(t.local_cache, fname))
        plugin.config.force_reprocessing = False
        plugin.config.disable_source_downloads = False
        return t

    def _df(self, date_value_pairs):
        return pl.DataFrame(
            {
                "Date": [p[0] for p in date_value_pairs],
                "Value": [float(p[1]) for p in date_value_pairs],
            }
        ).with_columns(pl.col("Date").str.to_date())

    def run_plugin(
        self,
        plugin_name,
        repo_scope=plugin.RepoScope.LOCAL,
        test_name="replete_1",
        prepare_only=False,
        log_level="info",
        disable_sheet_downloads=False,
        disable_database_downloads=False,
        disable_drive_downloads=False,
        disable_source_downloads=False,
        disable_sheet_uploads=True,
        disable_database_uploads=True,
        disable_drive_uploads=True,
        enable_rerun=True,
        force_reprocessing=False,
        force_downloads=False,
        today=None,
        counter_asserts=None,
        custom_asserts=None,
        file_asserts=None,
        rerun_errored=None,
    ):
        global _ASSERT_PASS_COL
        if file_asserts is None:
            file_asserts = {}
        if custom_asserts is None:
            custom_asserts = []
        if not disable_database_uploads:
            raise ValueError("disable_database_uploads must be True")
        if not disable_sheet_uploads and repo_scope == plugin.RepoScope.RELEASE:
            raise ValueError("disable_sheet_uploads must be True when repo_scope is RELEASE")
        if not disable_drive_uploads and repo_scope == plugin.RepoScope.RELEASE:
            raise ValueError("disable_drive_uploads must be True when repo_scope is RELEASE")
        plugin.config.log_level = log_level
        plugin.config.repo_scope = repo_scope
        plugin.config.force_reprocessing = force_reprocessing
        plugin.config.force_downloads = force_downloads
        plugin.config.disable_source_downloads = disable_source_downloads
        plugin.config.disable_sheet_downloads = disable_sheet_downloads
        plugin.config.disable_database_downloads = disable_database_downloads
        plugin.config.disable_drive_downloads = disable_drive_downloads
        plugin.config.disable_drive_uploads = disable_drive_uploads
        plugin.config.disable_sheet_uploads = disable_sheet_uploads
        plugin.config.disable_database_uploads = disable_database_uploads
        fixture_file = join(DIR_ROOT, "src/test/resources/repos", repo_scope, plugin_name, test_name, "fixture.toml")
        if today is None and isfile(fixture_file):
            with open(fixture_file, "rb") as toml_file:
                today = tomllib.load(toml_file).get("today")
        plugin.config.clock = None if today is None else datetime.datetime.fromisoformat(today)
        plugin.database_close()
        os.environ["WRANGLE_DATABASE_HOST"] = os.environ["POSTGRES_IP_PROD"]
        plugin.database_open()
        dir_target = join(DIR_ROOT, "target")
        if not isdir(dir_target):
            os.makedirs(dir_target)
        plugin_module = getattr(importlib.import_module(f"wrangle.plugin.{plugin_name}"), plugin_name.title())()
        print(flush=True)
        self._load_caches(plugin_module, join(DIR_ROOT, "src/test/resources/repos", repo_scope, plugin_name, test_name, "data"))
        label = f"{{:<22}} {f'[{plugin_name.title()}]':<15}   {f'[{repo_scope.name}]':<10}   {f'[{test_name}]'}"

        def _print(stage):
            print(("\n" if stage.startswith("STARTING") else "") + label.format(stage) + ("\n" if stage.startswith("FINISHED") else ""), flush=True)

        if not prepare_only:
            _print("STARTING (run)")
            plugin_module.run()
            _print("FINISHED (run)")
            self._save_pass_snapshot(plugin_module, 1)
            run_counters = plugin_module.get_counters()
            _print("STARTING (assert)")
            assert_started = time.time()
            print_log("Assert", "Starting ...")
            self._assert_counters(run_counters, counter_asserts)
            print_log("Assert", f"Finished in [{time.time() - assert_started:.3f}] sec")
            _print("FINISHED (assert)")
            if not enable_rerun:
                _print("STARTING (assert)")
                assert_started = time.time()
                print_log("Assert", "Starting ...")
                self._assert_outputs(plugin_module, file_asserts, enable_rerun=False)
                print_log("Assert", f"Finished in [{time.time() - assert_started:.3f}] sec")
                _print("FINISHED (assert)")
            else:
                first_counters = copy.deepcopy(run_counters)
                if not plugin.config.disable_drive_uploads and plugin_module.remote_repos.drive_folder is not None:
                    local_names = {basename(path).lower() for path in glob.glob(f"{plugin_module.local_cache}/*") if isfile(path) and not basename(path).startswith(("_", "~$"))}
                    listed_deadline = time.time() + 60
                    while local_names - {drive_file["name"].lower() for drive_file in drive_list(plugin_module.remote_repos.drive_folder)[1]}:
                        if time.time() > listed_deadline:
                            self.fail(f"Drive listing never showed uploaded files [{plugin_module.remote_repos.drive_folder}]")
                        time.sleep(2)
                plugin_module.reset_counters()
                _print("STARTING (rerun)")
                plugin_module.run()
                _print("FINISHED (rerun)")
                self._save_pass_snapshot(plugin_module, 2)
                noop_counters = plugin_module.get_counters()
                _print("STARTING (assert)")
                assert_started = time.time()
                print_log("Assert", "Starting ...")
                self._assert_counters(noop_counters, merge_asserts(ASSERT_NOOP, {"counter_equals": {source: {plugin.CTR_ACT_ERRORED: count} for source, count in (rerun_errored or {}).items()}}))
                print_log("Assert", f"Finished in [{time.time() - assert_started:.3f}] sec")
                _print("FINISHED (assert)")
                second_counters = copy.deepcopy(noop_counters)
                plugin_module.reset_counters()
                _print("STARTING (reprocess)")
                plugin.config.force_reprocessing = True
                plugin.config.disable_database_downloads = True
                plugin.config.disable_sheet_downloads = True
                plugin_module.run()
                plugin.config.force_reprocessing = force_reprocessing
                plugin.config.disable_database_downloads = disable_database_downloads
                plugin.config.disable_sheet_downloads = disable_sheet_downloads
                _print("FINISHED (reprocess)")
                self._save_pass_snapshot(plugin_module, 3)
                reload_counters = plugin_module.get_counters()
                _print("STARTING (assert)")
                assert_started = time.time()
                print_log("Assert", "Starting ...")
                self._assert_counters(reload_counters, merge_asserts(ASSERT_RELOAD, {"counter_equals": {source: {plugin.CTR_ACT_ERRORED: count} for source, count in (rerun_errored or {}).items()}}))
                print_log("Assert", f"Finished in [{time.time() - assert_started:.3f}] sec")
                _print("FINISHED (assert)")
                _print("STARTING (assert)")
                assert_started = time.time()
                print_log("Assert", "Starting ...")
                self._assert_outputs(plugin_module, file_asserts, enable_rerun=True)
                print_log("Assert", f"Finished in [{time.time() - assert_started:.3f}] sec")
                _print("FINISHED (assert)")
                _print("STARTING (assert)")
                assert_started = time.time()
                print_log("Assert", "Starting ...")
                self._assert_customs(custom_asserts, first_counters, second_counters, reload_counters, plugin_module.local_cache)
                print_log("Assert", f"Finished in [{time.time() - assert_started:.3f}] sec")
                _print("FINISHED (assert)")

    def _bank_run(
        self,
        test_name,
        today="2026-01-15T12:00:00",
        source=False,
        sheet_downloads=None,
        rerun=True,
        force=False,
        downloads=False,
        errored=None,
        standing=0,
        counters=None,
        file_asserts=None,
        custom_asserts=None,
    ):
        bank_api_offline(test_name)
        if sheet_downloads is not None:
            sheet_download_offline(sheet_downloads)
        drive = bank_drive_offline(test_name) is not None
        self.run_plugin(
            "bank",
            plugin.RepoScope.LOCAL,
            test_name,
            log_level="info",
            disable_sheet_downloads=True,
            disable_database_downloads=True,
            disable_drive_downloads=True,
            disable_source_downloads=not source,
            disable_sheet_uploads=True,
            disable_database_uploads=True,
            disable_drive_uploads=not drive,
            enable_rerun=rerun,
            force_reprocessing=force,
            force_downloads=downloads,
            today=today,
            rerun_errored={plugin.CTR_SRC_DATA: standing} if standing else None,
            counter_asserts=merge_asserts(
                merge_asserts(
                    ASSERT_RUN,
                    {
                        "counter_equals": {
                            counter: {plugin.CTR_ACT_ERRORED: (errored or {}).get(counter, 0) + (standing if counter == plugin.CTR_SRC_DATA else 0)}
                            for counter in (plugin.CTR_SRC_SOURCES, plugin.CTR_SRC_FILES, plugin.CTR_SRC_DATA, plugin.CTR_SRC_EGRESS)
                        }
                    },
                ),
                {"counter_equals": counters or {}},
            ),
            custom_asserts=custom_asserts,
            file_asserts=file_asserts,
        )

    def _bank_unusable(self, test_name, file_asserts=None):
        self._bank_run(
            test_name,
            rerun=False,
            force=True,
            errored={plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "__bank_balances_current.csv": [assert_file_size(min_rows=1, max_rows=1), assert_file_column_values("Account", ["Raw One"])],
                "__bank_logs.csv": [assert_file_column_values("Code", ["TAB_UNUSABLE"])],
                **(file_asserts or {}),
            },
        )

    def _save_pass_snapshot(self, plugin_module, pass_number):
        suffix_map = {
            1: "_1_run",
            2: "_2_rerun",
            3: "_3_reprocess",
        }
        for filename in os.listdir(plugin_module.local_cache):
            if re.match(r"^_.*\.csv$", filename) and not re.search(r"_\d_(run|rerun|reprocess)\.csv$", filename):
                source_path = join(plugin_module.local_cache, filename)
                dest_path = join(plugin_module.local_cache, f"{filename[:-4]}{suffix_map[pass_number]}.csv")
                shutil.copy(str(source_path), str(dest_path))

    def _load_caches(self, plugin_module, source):
        if not isdir(source):
            raise FileNotFoundError(f"Test data directory [{source}] does not exist")
        shutil.rmtree(plugin_module.local_cache, ignore_errors=True)
        shutil.copytree(source, plugin_module.local_cache, ignore=shutil.ignore_patterns(".git*", "~$*"))
        fixture_path = join(dirname(source), "fixture.toml")
        if isfile(fixture_path):
            with open(fixture_path, "rb") as fixture_file:
                mtimes = tomllib.load(fixture_file).get("mtimes", {})
            for file_name in sorted(os.listdir(plugin_module.local_cache), key=lambda name: name in mtimes):
                stamp = mtimes.get(file_name, mtimes.get("*"))
                if stamp is not None:
                    stamp_seconds = datetime.datetime.fromisoformat(stamp).timestamp()
                    os.utime(join(plugin_module.local_cache, file_name), (stamp_seconds, stamp_seconds))
        plugin_module.print_log(f"Files written from [{source}] to [{plugin_module.local_cache}]")

    def _assert_outputs(self, plugin_module, verifications, enable_rerun=False):
        global _ASSERT_FILE_EQUAL_SEEN
        _ASSERT_FILE_EQUAL_SEEN.clear()
        try:
            for filename, funcs in verifications.items():
                if filename.endswith("*.csv"):
                    stem = filename[:-5]
                    expanded = [f"{stem}_1_run.csv"] if enable_rerun else [f"{stem}.csv"]
                else:
                    expanded = [filename]
                for expanded_filename in expanded:
                    file_path = join(plugin_module.local_cache, expanded_filename)
                    if expanded_filename.endswith(".csv"):
                        pass_match = re.search(r"(_\d_(run|rerun|reprocess))\.csv$", expanded_filename)
                        pass_suffix = pass_match.group(1) if pass_match else ""
                        base_stem = expanded_filename[:-4][: len(expanded_filename) - 4 - len(pass_suffix)]
                        versioned = sorted(
                            (int(version_match.group(1)), path)
                            for path in glob.glob(join(plugin_module.local_cache, f"{base_stem}_v*{pass_suffix}.csv"))
                            if (version_match := re.fullmatch(rf"{re.escape(base_stem)}_v(\d+){re.escape(pass_suffix)}\.csv", basename(path)))
                        )
                        if versioned:
                            file_path = versioned[-1][1]
                    for func in funcs:
                        started = time.time()
                        result = func(file_path, filename)
                        elapsed = time.time() - started
                        if result is not None:
                            self.fail(f"Assertion [{func.__name__}] failed for [{expanded_filename}]. {result}")
                        else:
                            if func.__name__ == "assert_file_equal":
                                continue
                            _print_assert_pass(f"{func.__name__}:{filename} ({_format_assert_elapsed(elapsed)})")
        finally:
            _ASSERT_FILE_EQUAL_SEEN.clear()

    def _assert_counters(self, actual, asserts):
        if not asserts:
            return
        comparators = [
            ("counter_equals", self.assertEqual, "equals", "!="),
            ("counter_less", self.assertLessEqual, "less than", ">="),
            ("counter_at_least", self.assertGreaterEqual, "at least", "<"),
        ]
        for comparator_key, assert_fn, label, op in comparators:
            if comparator_key not in asserts:
                continue
            for counter_source, actions in asserts[comparator_key].items():
                for counter_action, expected in actions.items():
                    started = time.time()
                    actual_value = actual.get(counter_source, {}).get(counter_action, 0)
                    assert_fn(actual_value, expected, f"Counter [{counter_source} {counter_action}] {label} assertion failed [{actual_value}] {op} [{expected}]")
                    verb = _COUNTER_COMPARATOR_VERBS.get(comparator_key, comparator_key)
                    source_slug = counter_source.lower().replace(" ", "_")
                    action_slug = counter_action.lower().replace(" ", "_")
                    name = f"assert_counter_{source_slug}_{action_slug}_{verb}_{expected}"
                    _print_assert_pass(f"{name} ({_format_assert_elapsed(time.time() - started)})", f"actual={actual_value}")
        explicit_errored = {source for source, actions in asserts.get("counter_equals", {}).items() if plugin.CTR_ACT_ERRORED in actions}
        for counter_source, actions in actual.items():
            if counter_source in explicit_errored:
                continue
            actual_value = actions.get(plugin.CTR_ACT_ERRORED, 0)
            if actual_value == 0:
                continue
            started = time.time()
            self.assertEqual(0, actual_value, f"Counter [{counter_source} {plugin.CTR_ACT_ERRORED}] equals assertion failed [{actual_value}] != [0]")
            source_slug = counter_source.lower().replace(" ", "_")
            action_slug = plugin.CTR_ACT_ERRORED.lower().replace(" ", "_")
            _print_assert_pass(f"assert_counter_{source_slug}_{action_slug}_equals_0 ({_format_assert_elapsed(time.time() - started)})", f"actual={actual_value}")

    def _assert_customs(self, assertions, first, second, third, local_cache):
        for custom_assert in assertions:
            started = time.time()
            result = custom_assert(first, second, third, local_cache=local_cache)
            elapsed = time.time() - started
            if result is not None:
                self.fail(f"Custom assert [{custom_assert.__name__}] failed. {result}")
            values_fn = getattr(custom_assert, "_pass_values", None)
            values = values_fn() if callable(values_fn) else []
            if isinstance(values, str) or not isinstance(values, Iterable):
                values = []
            actuals = [v for v in values if isinstance(v, str) and v.startswith("actual=")]
            _print_assert_pass(f"{custom_assert.__name__} ({_format_assert_elapsed(elapsed)})", *actuals)

    def setUp(self):
        print(flush=True)
        _load_csv.cache_clear()
        shutil.rmtree(join(DIR_ROOT, "target", "data"), ignore_errors=True)
        os.makedirs(join(DIR_ROOT, "target", "data"))
        shutil.rmtree(join(DIR_ROOT, "target", "runtime-unit"), ignore_errors=True)
        os.makedirs(join(DIR_ROOT, "target", "runtime-unit"))
        reset_config(log="info")

    def tearDown(self):
        mock.patch.stopall()
        reset_config()


def _print_assert_pass(name, *values):
    actuals = [str(v)[7:] for v in values if str(v).startswith("actual=")]
    line = f"PASS [{name}]"
    if actuals:
        print(f"{line:<{_ASSERT_PASS_COL}}{'    ' + ' '.join(f'[{a}]' for a in actuals)}", flush=True)
    else:
        print(line, flush=True)


def _format_assert_elapsed(seconds):
    return f"{f'{seconds:.3f}'.rstrip('0').rstrip('.')}s"


_NUMERIC_DTYPES = (pl.Float32, pl.Float64, pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64)
_STR_DTYPES = (pl.String, pl.Utf8, pl.Null)


def _is_string_col(name, dtype):
    return name != "Date" and dtype in _STR_DTYPES


def _first_true_index(mask_series: pl.Series | bool):
    if isinstance(mask_series, bool):
        return 0 if mask_series else None
    indices = mask_series.arg_true()
    return None if len(indices) == 0 else int(indices[0])


def _count_leading_zero_rows(csv_df, numeric_cols):
    if not numeric_cols:
        return 0
    mask = csv_df.select(pl.any_horizontal((pl.col(c) == 0) & pl.col(c).is_not_null() for c in numeric_cols).alias("z"))["z"]
    first_false = _first_true_index(~mask)
    return len(mask) if first_false is None else int(first_false)


def _count_trailing_zero_rows(csv_df, numeric_cols):
    if not numeric_cols:
        return 0
    mask = csv_df.select(pl.any_horizontal((pl.col(c) == 0) & pl.col(c).is_not_null() for c in numeric_cols).alias("z"))["z"]
    first_false_from_end = _first_true_index(~mask.reverse())
    return len(mask) if first_false_from_end is None else int(first_false_from_end)


def _count_leading_none_rows(csv_df, cols):
    if not cols:
        return 0
    mask = csv_df.select(pl.any_horizontal(pl.col(c).is_null() for c in cols).alias("n"))["n"]
    first_false = _first_true_index(~mask)
    return len(mask) if first_false is None else int(first_false)


def _count_trailing_none_rows(csv_df, cols):
    if not cols:
        return 0
    mask = csv_df.select(pl.any_horizontal(pl.col(c).is_null() for c in cols).alias("n"))["n"]
    first_false_from_end = _first_true_index(~mask.reverse())
    return len(mask) if first_false_from_end is None else int(first_false_from_end)


@functools.cache
def _load_csv(file_path):
    return pl.read_csv(file_path, try_parse_dates=True)


def _filter_cols(csv_df, include=None, exclude=None):
    cols = csv_df.columns
    if include is not None:
        cols = [c for c in cols if re.search(include, c)]
    if exclude is not None:
        cols = [c for c in cols if not re.search(exclude, c)]
    return cols


def _files_equal_binary(path_1, path_2):
    try:
        result = subprocess.run(["cmp", "-s", path_1, path_2], check=False)
        return result.returncode == 0
    except (FileNotFoundError, OSError):
        return filecmp.cmp(path_1, path_2, shallow=False)


def assert_file_does_exist():
    def _assert(file_path, *_):
        if not isfile(file_path):
            msg = f"assert_file_does_exist: [{basename(file_path)}] does not exist"
            dataframe_print("Assert", pl.DataFrame(), msg, level="error")
            return msg
        return None

    _assert.__name__ = "assert_file_does_exist"
    return _assert


def assert_file_does_not_exist():
    def _assert(file_path, *_):
        if isfile(file_path):
            msg = f"assert_file_does_not_exist: [{basename(file_path)}] exists"
            dataframe_print("Assert", pl.DataFrame(), msg, level="error")
            return msg
        return None

    _assert.__name__ = "assert_file_does_not_exist"
    return _assert


def assert_file_size(min_rows=1, max_rows=None):
    def _assert(file_path, *_):
        csv_df = _load_csv(file_path)
        count = len(csv_df)
        if count < min_rows:
            msg = f"{_assert.__name__}: [{basename(file_path)}] expected >={min_rows} rows, got {count}"
            dataframe_print("Assert", csv_df, msg, level="error")
            return msg
        if max_rows is not None and count > max_rows:
            msg = f"{_assert.__name__}: [{basename(file_path)}] expected <={max_rows} rows, got {count}"
            dataframe_print("Assert", csv_df, msg, level="error")
            return msg
        return None

    _assert.__name__ = f"assert_file_size_{min_rows}_{max_rows}_rows"
    return _assert


def assert_file_nones_per_row(max_nones=0, after_first_rows=False, after_last_rows=False, include=None, exclude=None):
    def _assert(file_path, *_):
        csv_df = _load_csv(file_path)
        cols = _filter_cols(csv_df, include, exclude)
        if not cols:
            return None
        if after_first_rows:
            data_df = csv_df.slice(_count_leading_none_rows(csv_df, cols))
        elif after_last_rows:
            data_df = csv_df.head(len(csv_df) - _count_trailing_none_rows(csv_df, cols))
        else:
            data_df = csv_df
        fail_rows = data_df.filter(pl.sum_horizontal(pl.col(c).is_null().cast(pl.Int32) for c in cols) > max_nones)
        if not fail_rows.is_empty():
            msg = f"{_assert.__name__}: [{basename(file_path)}] rows with >{max_nones} nones"
            dataframe_print("Assert", fail_rows, msg, level="error")
            return msg
        return None

    _assert.__name__ = f"assert_file_max_{max_nones}_nones_per_row" + ("_after_first_rows" if after_first_rows else "") + ("_after_last_rows" if after_last_rows else "")
    return _assert


def assert_file_nones_per_col(max_nones=0, after_first_rows=False, after_last_rows=False, include=None, exclude=None):
    def _assert(file_path, *_):
        csv_df = _load_csv(file_path)
        cols = _filter_cols(csv_df, include, exclude)
        if not cols:
            return None
        if after_first_rows:
            violations = csv_df.select([(pl.col(c).is_null() & pl.col(c).is_not_null().cast(pl.UInt32).cum_sum().gt(0)).sum().alias(c) for c in cols])
        elif after_last_rows:
            violations = csv_df.select([(pl.col(c).is_null() & pl.col(c).is_not_null().reverse().cast(pl.UInt32).cum_sum().reverse().gt(0)).sum().alias(c) for c in cols])
        else:
            violations = csv_df.select([pl.col(c).null_count().alias(c) for c in cols])
        failed = [c for c in cols if violations[c][0] > max_nones]
        if failed:
            msg = f"{_assert.__name__}: [{basename(file_path)}] columns with >{max_nones} nones: {failed}"
            dataframe_print("Assert", csv_df.select(failed), msg, level="error")
            return msg
        return None

    _assert.__name__ = f"assert_file_max_{max_nones}_nones_per_col" + ("_after_first_rows" if after_first_rows else "") + ("_after_last_rows" if after_last_rows else "")
    return _assert


def assert_file_zeroes_per_row(max_zeroes=0, after_first_rows=False, after_last_rows=False, include=None, exclude=None):
    def _assert(file_path, *_):
        csv_df = _load_csv(file_path)
        numeric_cols = [col for col in _filter_cols(csv_df, include, exclude) if type(csv_df.schema[col]) in _NUMERIC_DTYPES]
        if not numeric_cols:
            return None
        if after_first_rows:
            data_df = csv_df.slice(_count_leading_zero_rows(csv_df, numeric_cols))
        elif after_last_rows:
            data_df = csv_df.head(len(csv_df) - _count_trailing_zero_rows(csv_df, numeric_cols))
        else:
            data_df = csv_df
        zero_count = pl.sum_horizontal((pl.col(c) == 0).cast(pl.Int32) for c in numeric_cols)
        fail_rows = data_df.filter(zero_count > max_zeroes)
        if not fail_rows.is_empty():
            msg = f"{_assert.__name__}: [{basename(file_path)}] rows with >{max_zeroes} zeros"
            dataframe_print("Assert", fail_rows, msg, level="error")
            return msg
        return None

    _assert.__name__ = f"assert_file_max_{max_zeroes}_zeroes_per_row" + ("_after_first_rows" if after_first_rows else "") + ("_after_last_rows" if after_last_rows else "")
    return _assert


def assert_file_zeroes_per_col(max_zeroes=0, after_first_rows=False, after_last_rows=False, include=None, exclude=None):
    def _assert(file_path, *_):
        csv_df = _load_csv(file_path)
        numeric_cols = [col for col in _filter_cols(csv_df, include, exclude) if type(csv_df.schema[col]) in _NUMERIC_DTYPES]
        if not numeric_cols:
            return None
        if after_first_rows:
            violations = csv_df.select([((pl.col(c).eq(0) & pl.col(c).is_not_null()) & (pl.col(c).ne(0) | pl.col(c).is_null()).cast(pl.UInt32).cum_sum().gt(0)).sum().alias(c) for c in numeric_cols])
        elif after_last_rows:
            violations = csv_df.select(
                [((pl.col(c).eq(0) & pl.col(c).is_not_null()) & (pl.col(c).ne(0) | pl.col(c).is_null()).reverse().cast(pl.UInt32).cum_sum().reverse().gt(0)).sum().alias(c) for c in numeric_cols]
            )
        else:
            violations = csv_df.select([(pl.col(c).eq(0) & pl.col(c).is_not_null()).sum().alias(c) for c in numeric_cols])
        failed = [c for c in numeric_cols if violations[c][0] > max_zeroes]
        if failed:
            msg = f"{_assert.__name__}: [{basename(file_path)}] columns with >{max_zeroes} zeros: {failed}"
            dataframe_print("Assert", csv_df.select(failed), msg, level="error")
            return msg
        return None

    _assert.__name__ = f"assert_file_max_{max_zeroes}_zeroes_per_col" + ("_after_first_rows" if after_first_rows else "") + ("_after_last_rows" if after_last_rows else "")
    return _assert


def assert_file_dates(start_date=None, end_date=None, end_date_at_least=None, max_gap_days=1, descending=None, contiguous=None):
    def _parse_date(_value):
        if _value is None:
            return None
        if isinstance(_value, str):
            return datetime.date.fromisoformat(_value)
        return _value

    def _assert(file_path, *_):
        csv_df = _load_csv(file_path)
        date_col = "Date" if "Date" in csv_df.columns else ("time" if "time" in csv_df.columns else None)
        if date_col is None:
            msg = f"assert_file_dates: [{basename(file_path)}] no Date column"
            dataframe_print("Assert", csv_df, msg, level="error")
            return msg
        raw_dates = csv_df[date_col].drop_nulls().to_list()
        if len(raw_dates) < 2:
            return None
        if descending is False:
            if raw_dates != sorted(raw_dates):
                msg = f"assert_file_dates: [{basename(file_path)}] dates not in ascending order, got {raw_dates[0]} .. {raw_dates[-1]}"
                dataframe_print("Assert", csv_df.head(3), msg, level="error")
                return msg
        elif descending is True:  # noqa: SIM102
            if raw_dates != sorted(raw_dates, reverse=True):
                msg = f"assert_file_dates: [{basename(file_path)}] dates not in descending order, got {raw_dates[0]} .. {raw_dates[-1]}"
                dataframe_print("Assert", csv_df.head(3), msg, level="error")
                return msg
        dates = sorted(set(raw_dates))
        if start_date is not None and dates[0] != _parse_date(start_date):
            msg = f"assert_file_dates: [{basename(file_path)}] expected start {start_date}, got {dates[0]}"
            dataframe_print("Assert", csv_df.head(1), msg, level="error")
            return msg
        if end_date is not None and dates[-1] != _parse_date(end_date):
            msg = f"assert_file_dates: [{basename(file_path)}] expected end {end_date}, got {dates[-1]}"
            dataframe_print("Assert", csv_df.tail(1), msg, level="error")
            return msg
        if end_date_at_least is not None and dates[-1] < _parse_date(end_date_at_least):
            msg = f"assert_file_dates: [{basename(file_path)}] expected end at least {end_date_at_least}, got {dates[-1]}"
            dataframe_print("Assert", csv_df.tail(1), msg, level="error")
            return msg
        if contiguous == "days":
            date_series = pl.Series(dates)
            diffs = date_series.diff().dt.total_days().slice(1)
            idx = _first_true_index(diffs > max_gap_days)
            if idx is not None:
                msg = f"assert_file_dates: [{basename(file_path)}] gap of {int(diffs[idx])} days between {dates[idx]} and {dates[idx + 1]} exceeds max {max_gap_days}"
                gap_df = csv_df.filter(pl.col(date_col).is_in([dates[idx], dates[idx + 1]]))
                dataframe_print("Assert", gap_df, msg, level="error")
                return msg
        elif contiguous == "months":
            date_series = pl.Series(dates)
            month_diffs = (date_series.dt.year() * 12 + date_series.dt.month()).diff().slice(1)
            idx = _first_true_index(month_diffs != 1)
            if idx is not None:
                msg = f"assert_file_dates: [{basename(file_path)}] non-consecutive months between {dates[idx]} and {dates[idx + 1]}"
                gap_df = csv_df.filter(pl.col(date_col).is_in([dates[idx], dates[idx + 1]]))
                dataframe_print("Assert", gap_df, msg, level="error")
                return msg
        elif contiguous == "years":
            date_series = pl.Series(dates)
            year_diffs = date_series.dt.year().diff().slice(1)
            idx = _first_true_index(year_diffs != 1)
            if idx is not None:
                msg = f"assert_file_dates: [{basename(file_path)}] non-consecutive years between {dates[idx]} and {dates[idx + 1]}"
                gap_df = csv_df.filter(pl.col(date_col).is_in([dates[idx], dates[idx + 1]]))
                dataframe_print("Assert", gap_df, msg, level="error")
                return msg
        return None

    _assert.__name__ = "assert_file_dates"
    return _assert


def assert_file_column_values(column, values, sort_by=None, raw=False):
    def _assert(file_path, *_):
        csv_df = pl.read_csv(file_path, infer_schema=False) if raw else _load_csv(file_path)
        actual = (csv_df.sort(sort_by) if sort_by is not None else csv_df)[column].cast(pl.Utf8).to_list()
        if actual != values:
            msg = f"assert_file_column_values: [{basename(file_path)}] column [{column}] expected {values}, got {actual}"
            dataframe_print("Assert", csv_df, msg, level="error")
            return msg
        return None

    _assert.__name__ = f"assert_file_column_values_{column.lower().replace(' ', '_')}"
    return _assert


def assert_file_column_distinct(column, count):
    def _assert(file_path, *_):
        csv_df = _load_csv(file_path)
        actual = csv_df[column].n_unique()
        if actual != count:
            msg = f"assert_file_column_distinct: [{basename(file_path)}] column [{column}] expected {count} distinct, got {actual}"
            dataframe_print("Assert", csv_df, msg, level="error")
            return msg
        return None

    _assert.__name__ = f"assert_file_column_distinct_{column.lower().replace(' ', '_')}_{count}"
    return _assert


def assert_file_columns(columns):
    def _assert(file_path, *_):
        actual = _load_csv(file_path).columns
        if actual != columns:
            msg = f"assert_file_columns: [{basename(file_path)}] expected columns {columns}, got {actual}"
            dataframe_print("Assert", pl.DataFrame(), msg, level="error")
            return msg
        return None

    _assert.__name__ = "assert_file_columns"
    return _assert


def assert_file_max_rows_per_value(column, max_rows):
    def _assert(file_path, *_):
        csv_df = _load_csv(file_path)
        over_df = csv_df.group_by(column).len().filter(pl.col("len") > max_rows)
        if len(over_df):
            msg = f"assert_file_max_rows_per_value: [{basename(file_path)}] column [{column}] values with >{max_rows} rows"
            dataframe_print("Assert", over_df, msg, level="error")
            return msg
        return None

    _assert.__name__ = f"assert_file_max_{max_rows}_rows_per_{column.lower().replace(' ', '_')}"
    return _assert


def assert_file_equal(exclude=None):
    def _assert(file_path, key_filename="", *_):
        global _ASSERT_FILE_EQUAL_SEEN
        stem = file_path[:-4]
        if stem.endswith("_1_run"):
            compare_path = stem.removesuffix("_1_run") + "_3_reprocess.csv"
        elif stem.endswith("_3_reprocess"):
            compare_path = stem.removesuffix("_3_reprocess") + "_1_run.csv"
        else:
            return None
        if not isfile(compare_path):
            return f"assert_file_equal: [{basename(file_path)}] comparison file does not exist [{basename(compare_path)}]"
        compare_key = tuple(sorted((abspath(file_path), abspath(compare_path))))
        if compare_key in _ASSERT_FILE_EQUAL_SEEN:
            return None
        _ASSERT_FILE_EQUAL_SEEN.add(compare_key)
        compare_started = time.time()
        if exclude is None and _files_equal_binary(file_path, compare_path):
            _print_assert_pass(f"assert_file_equal_compare_binary:{key_filename} ({_format_assert_elapsed(time.time() - compare_started)})")
            return None
        df1 = _load_csv(file_path)
        df2 = _load_csv(compare_path)
        compare_type = "dataframe"
        if exclude is not None:
            df1 = df1.drop([c for c in df1.columns if re.search(exclude, c)])
            df2 = df2.drop([c for c in df2.columns if re.search(exclude, c)])
            compare_type = f"dataframe_exclude[{exclude}]"
        if not df1.equals(df2):
            msg = f"assert_file_equal: [{basename(file_path)}] vs [{basename(compare_path)}] run and reprocess differ"
            csv_diff.diff_print(file_path, compare_path, exclude)
            return msg
        _print_assert_pass(f"assert_file_equal_compare_{compare_type}:{key_filename} ({_format_assert_elapsed(time.time() - compare_started)})")
        return None

    _assert.__name__ = "assert_file_equal"
    return _assert


def assert_file_subset(keys=None, value="value"):
    def _assert(file_path, key_filename="", *_):
        stem = file_path[:-4]
        if not stem.endswith("_1_run"):
            return None
        superset_path = stem.removesuffix("_1_run") + "_3_reprocess.csv"
        if not isfile(superset_path):
            return f"assert_file_subset: [{basename(file_path)}] superset file does not exist [{basename(superset_path)}]"
        compare_started = time.time()
        subset_df = _load_csv(file_path)
        superset_df = _load_csv(superset_path)
        if len(subset_df) == 0:
            return None
        key_columns = keys if keys is not None else [column for column in subset_df.columns if column != value]
        joined = subset_df.join(superset_df.select([*key_columns, value]), on=key_columns, how="left", suffix="_superset")
        missing = joined.filter(pl.col(f"{value}_superset").is_null())
        if len(missing) > 0:
            dataframe_print("Assert", missing, f"assert_file_subset: [{basename(file_path)}] rows absent from [{basename(superset_path)}]", level="error")
            return f"assert_file_subset: [{basename(file_path)}] has [{len(missing)}] row(s) not present in [{basename(superset_path)}]"
        mismatched = joined.filter(pl.col(value) != pl.col(f"{value}_superset"))
        if len(mismatched) > 0:
            dataframe_print("Assert", mismatched, f"assert_file_subset: [{basename(file_path)}] value differs from [{basename(superset_path)}]", level="error")
            return f"assert_file_subset: [{basename(file_path)}] has [{len(mismatched)}] row(s) whose value differs from [{basename(superset_path)}]"
        _print_assert_pass(f"assert_file_subset:{key_filename} ({_format_assert_elapsed(time.time() - compare_started)})")
        return None

    _assert.__name__ = "assert_file_subset"
    return _assert


def assert_custom_rows_delta(equals=None, at_least=None, at_most=None, state=None):
    if equals is None and at_least is None and at_most is None:
        raise ValueError("assert_custom_rows_delta requires one of equals, at_least, or at_most")

    def _assert(first, _, third, local_cache=""):
        if state is None:
            current_rows = third.get(plugin.CTR_SRC_DATA, {}).get(plugin.CTR_ACT_CURRENT_ROWS, 0)
            previous_rows = first.get(plugin.CTR_SRC_DATA, {}).get(plugin.CTR_ACT_PREVIOUS_ROWS, 0)
        else:

            def state_rows(kind, suffix):
                state_file = join(local_cache, f"__{state}_{kind}{suffix}.csv")
                return len(_load_csv(state_file)) if isfile(state_file) else 0

            current_rows = state_rows("current", "_3_reprocess")
            previous_rows = state_rows("previous", "_1_run")
        delta = current_rows - previous_rows
        _assert.last_delta = delta  # pyright: ignore[reportFunctionMemberAccess]
        if equals is not None and delta != equals:
            return f"assert_rows_delta: expected delta == {equals}, got {delta} (current_rows={current_rows}, previous_rows={previous_rows})"
        if at_least is not None and delta < at_least:
            return f"assert_rows_delta: expected delta > {at_least}, got {delta} (current_rows={current_rows}, previous_rows={previous_rows})"
        if at_most is not None and delta > at_most:
            return f"assert_rows_delta: expected delta < {at_most}, got {delta} (current_rows={current_rows}, previous_rows={previous_rows})"
        return None

    parts = [f"is_{equals}" if equals is not None else None, f"at_least_{at_least}" if at_least is not None else None, f"at_most_{at_most}" if at_most is not None else None]
    suffix = "_".join(p for p in parts if p is not None)
    _assert.last_delta = None  # pyright: ignore[reportFunctionMemberAccess]
    _assert._pass_values = lambda: [f"actual={_assert.last_delta}"]  # pyright: ignore[reportFunctionMemberAccess]
    _assert.__name__ = f"assert_custom_rows_delta{'' if state is None else f'_{state}'}_{suffix}"
    return _assert


def merge_asserts(base, addition):
    merged = copy.deepcopy(base)
    for test in addition:
        if test not in merged:
            merged[test] = addition[test]
        else:
            for source in addition[test]:
                if source not in merged[test]:
                    merged[test][source] = addition[test][source]
                else:
                    merged[test][source].update(addition[test][source])
    return merged


ASSERT_NONE = {}

ASSERT_RUN = {
    "counter_at_least": {
        plugin.CTR_SRC_SOURCES: {
            plugin.CTR_ACT_DOWNLOADED: 0,
        },
        plugin.CTR_SRC_FILES: {
            plugin.CTR_ACT_PROCESSED: 0,
        },
        plugin.CTR_SRC_DATA: {
            plugin.CTR_ACT_CURRENT_ROWS: 0,
            plugin.CTR_ACT_UPDATE_ROWS: 0,
            plugin.CTR_ACT_DELTA_ROWS: 0,
        },
    },
}

ASSERT_NOOP = {
    "counter_equals": {
        plugin.CTR_SRC_SOURCES: {
            plugin.CTR_ACT_DOWNLOADED: 0,
            plugin.CTR_ACT_UPLOADED: 0,
        },
        plugin.CTR_SRC_FILES: {
            plugin.CTR_ACT_PROCESSED: 0,
        },
        plugin.CTR_SRC_DATA: {
            plugin.CTR_ACT_UPDATE_COLUMNS: 0,
            plugin.CTR_ACT_UPDATE_ROWS: 0,
            plugin.CTR_ACT_DELTA_COLUMNS: 0,
            plugin.CTR_ACT_DELTA_ROWS: 0,
        },
        plugin.CTR_SRC_EGRESS: {
            plugin.CTR_ACT_SHEET_COLUMNS: 0,
            plugin.CTR_ACT_SHEET_ROWS: 0,
            plugin.CTR_ACT_DATABASE_COLUMNS: 0,
            plugin.CTR_ACT_DATABASE_ROWS: 0,
        },
    },
    "counter_at_least": {
        plugin.CTR_SRC_SOURCES: {
            plugin.CTR_ACT_CACHED: 0,
        },
        plugin.CTR_SRC_FILES: {
            plugin.CTR_ACT_SKIPPED: 0,
        },
    },
}

ASSERT_RELOAD = {
    "counter_equals": {
        plugin.CTR_SRC_SOURCES: {
            plugin.CTR_ACT_DOWNLOADED: 0,
        },
        plugin.CTR_SRC_DATA: {
            plugin.CTR_ACT_PREVIOUS_ROWS: 0,
        },
    },
    "counter_at_least": {
        plugin.CTR_SRC_FILES: {
            plugin.CTR_ACT_PROCESSED: 0,
        },
        plugin.CTR_SRC_DATA: {
            plugin.CTR_ACT_CURRENT_ROWS: 0,
            plugin.CTR_ACT_UPDATE_ROWS: 0,
            plugin.CTR_ACT_DELTA_ROWS: 0,
        },
    },
}

for environment_key, environment_value in list(plugin.load_profile(join(DIR_ROOT, ".env")).items()):
    os.environ[environment_key] = environment_value


def reset_config(log="warning"):
    plugin.config.log_level = log
    plugin.config.repo_scope = plugin.RepoScope.RELEASE
    plugin.config.cache_dir = abspath(join(DIR_ROOT, "target", "data"))
    plugin.config.force_reprocessing = False
    plugin.config.force_downloads = False
    plugin.config.force_uploads = False
    plugin.config.disable_drive_uploads = True
    plugin.config.disable_sheet_uploads = True
    plugin.config.disable_database_uploads = True
    plugin.config.disable_drive_downloads = True
    plugin.config.disable_source_downloads = False
    plugin.config.disable_sheet_downloads = False
    plugin.config.disable_database_downloads = False
    plugin.config.clock = None
    plugin.database_close()


def drive_delete(drive_dir, file_name):
    if drive_dir is None or file_name is None:
        return
    service, drive_files = drive_list(drive_dir, f"name = '{file_name}'")
    for drive_file in drive_files:
        service.files().delete(fileId=drive_file["id"]).execute()


def drive_list(drive_dir, query=None):
    credentials = google.oauth2.service_account.Credentials.from_service_account_file(get_file(".google_service_account.json"), scopes=["https://www.googleapis.com/auth/drive"])
    service = build("drive", "v3", credentials=credentials, cache_discovery=False)
    drive_files = []
    token = None
    while True:
        response = (
            service.files()
            .list(
                q=f"'{drive_dir}' in parents and trashed = false" + ("" if query is None else f" and {query}"), spaces="drive", fields="nextPageToken, files(id, name)", pageSize=1000, pageToken=token
            )
            .execute()
        )
        drive_files.extend(response.get("files", []))
        token = response.get("nextPageToken")
        if not token:
            return service, drive_files


def bank_api_offline(test_name, scope="local"):
    fixture_dir = join(DIR_ROOT, "src/test/resources/repos", scope, "bank", test_name, "data")

    def _rows(resource):
        with open(join(fixture_dir, f"_redbark_{resource}.csv")) as resource_file:
            return [{key: (value if value != "" else None) for key, value in row.items()} for row in csv.DictReader(resource_file)]

    def _urlopen(request, *_args, **_kwargs):
        url = urllib.parse.urlparse(request.full_url)
        query = {key: values[0] for key, values in urllib.parse.parse_qs(url.query).items()}
        resource = url.path.rsplit("/", 1)[-1]
        if resource == "transactions" and isfile(join(fixture_dir, "_redbark_errors.csv")):
            for error in _rows("errors"):
                if error["accountId"] == query.get("accountId"):
                    raise urllib.error.HTTPError(request.full_url, int(str(error["code"])), "offline fixture error", Message(), None)
        if resource == "transactions" and not isfile(join(fixture_dir, "_redbark_transactions.csv")):
            rows = []
        elif not isfile(join(fixture_dir, f"_redbark_{resource}.csv")):
            raise urllib.error.HTTPError(request.full_url, 500, "offline fixture absent", Message(), None)
        elif resource == "balances":
            rows = [row for row in _rows(resource) if row.get("accountId") in query["accountIds"].split(",")]
        elif resource == "transactions":
            rows = [
                row
                for row in _rows(resource)
                if row.get("accountId") == query["accountId"] and ("from" not in query or (row.get("date") or "") >= query["from"]) and ("to" not in query or (row.get("date") or "") <= query["to"])
            ]
        else:
            rows = _rows(resource)
        offset, limit = int(query.get("offset", 0)), int(query.get("limit", len(rows) or 1))
        return urllib.response.addinfourl(
            io.BytesIO(json.dumps({"data": rows[offset : offset + limit], "pagination": {"hasMore": offset + limit < len(rows)}}).encode()), Message(), request.full_url, 200
        )

    mock.patch("wrangle.plugin._sources.urllib.request.urlopen", _urlopen).start()
    mock.patch("wrangle.plugin._throttle.time.sleep", lambda _seconds: None).start()


def bank_drive_offline(test_name):
    drive_dir = join(DIR_ROOT, "src/test/resources/repos/local/bank", test_name, "drive")
    if not isdir(drive_dir):
        return None
    drive = _FakeDrive()
    for name in sorted(os.listdir(drive_dir)):
        with open(join(drive_dir, name), "rb") as drive_file:
            drive.put(name, drive_file.read())
    drive.patch()
    mock.patch.object(plugin.Repos, "__getattr__", lambda _self, name: "folder" if name == "drive_folder" else None).start()
    return drive


def sheet_download_offline(downloads=1):
    served = {"lists": 0}

    def _sheet_download(self, drive_key, workbook_name, sheet_name=None, *_args, **_kwargs):
        sheet_names = sheet_name if isinstance(sheet_name, list) else [sheet_name]
        results = {}
        for name in sheet_names:
            cache_name = (workbook_name if name is None else f"{workbook_name}_{name}").lower()
            file_path = self._sheet_cache_path(cache_name)
            moved_path = abspath(f"{self.local_cache}/_sheet_{cache_name}_moved.csv")
            if file_path is None:
                results[name] = DownloadResult(DownloadStatus.FAILED, [])
            elif not isinstance(sheet_name, list) and isfile(moved_path):
                results[name] = DownloadResult(DownloadStatus.DOWNLOADED, [moved_path])
            else:
                results[name] = DownloadResult(DownloadStatus.DOWNLOADED if isinstance(sheet_name, list) and served["lists"] < downloads else DownloadStatus.CACHED, [file_path])
        if isinstance(sheet_name, list):
            served["lists"] += 1
            return results
        return results[sheet_name]

    mock.patch.object(Plugin, "sheet_download", _sheet_download).start()


def stock_download_offline(new_file_names):
    served_files = set()

    def _stock_download(self, local_path: str, *_args, **_kwargs):
        local_path = abspath(local_path).lower()
        file_name = basename(local_path)
        if isfile(local_path):
            if file_name in new_file_names and file_name not in served_files:
                served_files.add(file_name)
                self.add_counter(plugin.CTR_SRC_SOURCES, plugin.CTR_ACT_DOWNLOADED)
                return DownloadResult(DownloadStatus.DOWNLOADED, [local_path])
            self.add_counter(plugin.CTR_SRC_SOURCES, plugin.CTR_ACT_CACHED)
            return DownloadResult(DownloadStatus.CACHED, [local_path])
        self.add_counter(plugin.CTR_SRC_SOURCES, plugin.CTR_ACT_SKIPPED)
        return DownloadResult(DownloadStatus.SKIPPED, [])

    mock.patch.object(Plugin, "stock_download", _stock_download).start()


class _Killed(BaseException):
    pass


class _FakeDrive:
    def __init__(self):
        self.files_by_id = {}
        self.clock = 1_700_000_000
        self.calls = collections.Counter()
        self.failures = []
        self.after_list = []

    def put(self, name, content):
        self.clock += 60
        existing = [drive_id for drive_id, drive_file in self.files_by_id.items() if drive_file["name"] == name and not drive_file["trashed"]]
        drive_id = existing[0] if existing and name not in ("activity.csv", "dup.csv", "same.csv") else f"Id{len(self.files_by_id)}"
        created = self.files_by_id[drive_id]["created"] if drive_id in self.files_by_id else self.clock
        self.files_by_id[drive_id] = {"name": name, "content": content, "modified": self.clock, "created": created, "trashed": False}
        return drive_id

    def live(self, name):
        return [drive_id for drive_id, drive_file in self.files_by_id.items() if drive_file["name"] == name and not drive_file["trashed"]]

    def content(self, name):
        return next(drive_file["content"] for drive_file in self.files_by_id.values() if drive_file["name"] == name and not drive_file["trashed"])

    def content_by_id(self, drive_id):
        return self.files_by_id[drive_id]["content"]

    def name_by_id(self, drive_id):
        return self.files_by_id[drive_id]["name"]

    def patch(self):
        drive = self

        class _Request:
            def __init__(self, result):
                self.result = result

            def execute(self):
                return self.result() if callable(self.result) else self.result

        class _Files:
            def list(self, q="", **_kwargs):
                def _listed():
                    drive.calls["list"] += 1
                    if drive.failures:
                        raise drive.failures.pop(0)
                    named = re.search(r"name = '((?:[^'\\]|\\.)*)'", q)
                    listed = {
                        "files": [
                            {
                                "id": drive_id,
                                "name": drive_file["name"],
                                "md5Checksum": hashlib.md5(drive_file["content"]).hexdigest(),
                                "createdTime": datetime.datetime.fromtimestamp(drive_file["created"], datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                                "modifiedTime": datetime.datetime.fromtimestamp(drive_file["modified"], datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                            }
                            for drive_id, drive_file in drive.files_by_id.items()
                            if not drive_file["trashed"] and (named is None or drive_file["name"] == re.sub(r"\\(.)", r"\1", named[1]))
                        ]
                    }
                    while drive.after_list:
                        drive.after_list.pop(0)()
                    return listed

                return _Request(_listed)

            def get_media(self, fileId):
                return fileId

            def create(self, body, media_body):
                drive.calls["upload"] += 1
                drive_id = f"Id{len(drive.files_by_id)}"
                with open(media_body, "rb") as media_file:
                    drive.files_by_id[drive_id] = {"name": body["name"], "content": media_file.read(), "modified": drive.clock, "created": drive.clock, "trashed": False}
                return _Request({"id": drive_id})

            def update(self, fileId, body, media_body=None):
                if "name" in body:
                    drive.files_by_id[fileId]["name"] = body["name"]
                if body.get("trashed"):
                    drive.files_by_id[fileId]["trashed"] = True
                if media_body is not None:
                    drive.calls["upload"] += 1
                    with open(media_body, "rb") as media_file:
                        drive.files_by_id[fileId]["content"] = media_file.read()
                return _Request({"id": fileId})

        class _Service:
            def files(self):
                return _Files()

        class _Download:
            def __init__(self, buffer, request):
                self.buffer, self.request = buffer, request

            def next_chunk(self):
                self.buffer.write(drive.files_by_id[self.request]["content"])
                return None, True

        mock.patch("wrangle.plugin._sources.build", lambda *_args, **_kwargs: _Service()).start()
        mock.patch("wrangle.plugin._sources.MediaIoBaseDownload", _Download).start()
        mock.patch("wrangle.plugin._sources.MediaFileUpload", lambda path: path).start()
        mock.patch("wrangle.plugin._sources.get_file", lambda name: name).start()
        mock.patch("google.oauth2.service_account.Credentials.from_service_account_file", lambda *_args, **_kwargs: None).start()
        mock.patch.object(Plugin, "_google_authorized_http", staticmethod(lambda _credentials: None)).start()


class PluginStub(Plugin):
    def _run(self):
        pass

    def __init__(self, name, drive_folder):
        super().__init__(
            name,
            repos=plugin.Repos(
                preview={"drive_folder": "PLACEHOLDER"},
                release={"drive_folder": drive_folder},
            ),
        )


def _load_fixture(scope: str, plugin_name: str, test_name: str) -> dict:
    path = join(DIR_ROOT, "src/test/resources/repos", scope, plugin_name, test_name, "fixture.toml")
    assert isfile(path), f"Fixture [{path}] not found, run [src/test/resources/repos/refresh.sh] to generate it"
    with open(path, "rb") as toml_file:
        fixture = tomllib.load(toml_file)
    cols_full = {
        "bank": len(BANK_BALANCES_STATE_SCHEMA) - len(BANK_BALANCES_KEY_COLUMNS) + len(BANK_TRANSACTIONS_STATE_SCHEMA) - len(BANK_TRANSACTIONS_KEY_COLUMNS),
        "currency": len(CURRENCY_COLUMNS),
        "interest": len(INTEREST_COLUMNS),
        "equity": (len(STOCK) + len(PORTFOLIO_TICKERS_ACTIVE) + len(PORTFOLIO_TICKERS_MANUAL) - len(PORTFOLIO_TICKERS_NODATA)) * len(DIMENSIONS_STATE),
    }
    if int(fixture.get("cols_data", -1)) < 0 and plugin_name in cols_full:
        fixture["cols_data"] = cols_full[plugin_name]
    return fixture


_ASSERT_FILE_EQUAL_SEEN = set()
_COUNTER_COMPARATOR_VERBS = {
    "counter_equals": "is",
    "counter_less": "less_than",
    "counter_at_least": "at_least",
}
_ASSERT_PASS_COL = 60

if __name__ == "__main__":
    sys.exit(
        pytest.main(
            [
                "-s",
                "-v",
                "--durations=50",
                "-o",
                f"cache_dir={join(DIR_ROOT, 'target/.pytest_cache')}",
                __file__,
            ]
        )
    )
