import sys
from os.path import dirname

sys.path.insert(0, dirname(__file__))

import copy
import csv
import dataclasses
import datetime
import filecmp
import functools
import glob
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
import pandas as pd
import polars as pl
import pytest
from googleapiclient.discovery import build

sys.path.append("../../../main/python")

from wrangle import main as wrangle_main
from wrangle import plugin
from wrangle.plugin import DownloadResult, DownloadStatus, Plugin, database
from wrangle.plugin.bank import BALANCES_KEY_COLUMNS as BANK_BALANCES_KEY_COLUMNS
from wrangle.plugin.bank import (
    BALANCES_SCHEMA,
    REPOS_BANK,
    TRANSACTIONS_SCHEMA,
    bank_flag,
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

    # No data at all, nothing committed and no error
    def test_bank_local_blank_1(self):
        self._bank_run(
            "blank_1",
            rerun=False,
            file_asserts={
                "__bank_balances_current.csv": [assert_file_does_not_exist()],
            },
        )

    # One unreadable balances file on forced reprocessing counts an errored file and commits nothing
    def test_bank_local_corrupt_1(self):
        self._bank_run(
            "corrupt_1",
            rerun=False,
            force=True,
            errored={plugin.CTR_SRC_FILES: 1},
            file_asserts={
                "__bank_balances_current.csv": [assert_file_size(min_rows=0, max_rows=0)],
            },
        )

    # A type 2 version renames one account from its from date, the tab with no committed snapshot re-deriving every balance
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

    # Two numbers share a name in sequence without error, a third account on no accounts row keeps its stored name and is unmapped
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

    # A padded key maps and an extra column is ignored, a version not yet valid keeps the stored name, while its from date in the future, a blank name and the same
    # number at another institution each count a source error
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
    def test_bank_local_missing_1(self):
        self._bank_run(
            "missing_1",
            rerun=False,
            force=True,
            file_asserts={
                "__bank_balances_current.csv": [
                    assert_file_size(min_rows=3, max_rows=3),
                    assert_file_column_values("Account", ["Raw One", "Raw Two", "Raw Three"], sort_by=["Balance"]),
                ],
            },
        )

    # A file with a row lacking its account id errors that file only, the other still commits
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

    # An unusable accounts tab maps nothing and counts one source error while the balances still commit under their stored names: two rows for one account on
    # one date, a header only, rows lacking a natural key, a missing natural key column, or an unparseable from date
    def test_bank_local_corrupt_3(self):
        self._bank_unusable("corrupt_3")

    def test_bank_local_corrupt_6(self):
        self._bank_unusable("corrupt_6")

    def test_bank_local_corrupt_7(self):
        self._bank_unusable("corrupt_7")

    def test_bank_local_corrupt_8(self):
        self._bank_unusable("corrupt_8")

    def test_bank_local_corrupt_9(self):
        self._bank_unusable("corrupt_9")

    # An empty accounts tab is unusable and drops the committed snapshot so the next usable tab re-derives every balance
    def test_bank_local_corrupt_5(self):
        self._bank_unusable("corrupt_5", {"__bank_accounts_dimension.csv": [assert_file_does_not_exist()]})

    # Two accounts holding one name on the same date are a source error while both readings commit under their own ids
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

    # A first live check with no files: the weekly accounts call appends the Redbark account missing from the tab as linked, the opening snapshot of both is
    # written with readings timed by their observed time and pinned ids, it sweeps the transactions, which have none, and reruns are fresh
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

    # A current balances file stamped an hour ago is fresh: nothing is requested, and the fresh cache commits the file it holds
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

    # A balances file stamped three hours ago is due: unchanged balances store nothing and only stamp it, and today's sweep is done so no transactions are requested
    def test_bank_local_partial_6(self):
        self._bank_run(
            "partial_6",
            source=True,
            counters={plugin.CTR_SRC_SOURCES: {plugin.CTR_ACT_DOWNLOADED: 1}, plugin.CTR_SRC_FILES: {plugin.CTR_ACT_PROCESSED: 1}},
            file_asserts={
                "redbark_balances_2026.csv": [assert_file_size(min_rows=2, max_rows=2)],
                "redbark_transactions_2026.csv": [assert_file_does_not_exist()],
            },
        )

    # A due check with a moved balance appends one reading timed by its observed time and sweeps the transactions, an account with nothing held and a blank from
    # date asking for the last seven years: postings land in the year files of their dates, one with its codes, and one older than seven years is not fetched
    def test_bank_local_partial_7(self):
        self._bank_run(
            "partial_7",
            standing=4,
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

    # The first check of a new year writes its opening snapshot of every linked account into a new year file and leaves the previous year's file untouched
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

    # The first check of a new year compares each reading to the previous year file's latest: none moved, so the opening snapshot is written and, today's sweep
    # done, no transactions are requested
    def test_bank_local_partial_46(self):
        self._bank_run(
            "partial_46",
            source=True,
            counters={plugin.CTR_SRC_SOURCES: {plugin.CTR_ACT_DOWNLOADED: 1}, plugin.CTR_SRC_FILES: {plugin.CTR_ACT_PROCESSED: 2}},
            file_asserts={
                "redbark_balances_2026.csv": [assert_file_size(min_rows=2, max_rows=2)],
                "redbark_transactions_2026.csv": [assert_file_does_not_exist()],
                "__bank_balances_current.csv": [assert_file_size(min_rows=4, max_rows=4)],
            },
        )

    # The first check of a new month appends its opening snapshot of every linked account to the year file though no balance moved, requesting no transactions,
    # and the stamped file is fresh on the rerun
    def test_bank_local_partial_36(self):
        self._bank_run(
            "partial_36",
            today="2026-02-02T12:00:00",
            source=True,
            counters={plugin.CTR_SRC_SOURCES: {plugin.CTR_ACT_DOWNLOADED: 1}, plugin.CTR_SRC_FILES: {plugin.CTR_ACT_PROCESSED: 1}},
            file_asserts={
                "redbark_balances_2026.csv": [
                    assert_file_size(min_rows=4, max_rows=4),
                    assert_file_dates(start_date="2026-01-15", end_date="2026-02-02"),
                ],
                "redbark_transactions_2026.csv": [assert_file_does_not_exist()],
                "__bank_balances_current.csv": [assert_file_size(min_rows=4, max_rows=4)],
            },
        )

    # An unreadable current balances file is kept and not queried into, counting an errored file
    def test_bank_local_corrupt_11(self):
        self._bank_run(
            "corrupt_11",
            source=True,
            rerun=False,
            errored={plugin.CTR_SRC_FILES: 1},
            counters={plugin.CTR_SRC_SOURCES: {plugin.CTR_ACT_DOWNLOADED: 0}},
            file_asserts={
                "redbark_balances_2026.csv": [assert_file_does_exist()],
                "__bank_balances_current.csv": [assert_file_size(min_rows=0, max_rows=0)],
            },
        )

    # Live balances duplicated, without a numeric value or for an unknown account count one source error, the valid one is stored
    def test_bank_local_corrupt_12(self):
        self._bank_run(
            "corrupt_12",
            source=True,
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "redbark_balances_2026.csv": [assert_file_size(min_rows=1, max_rows=1), assert_file_column_values("Account", ["One"])],
            },
        )

    # A balances response with no balances is a source error and the linked account absent from it a data error, writing no file
    def test_bank_local_corrupt_13(self):
        self._bank_run(
            "corrupt_13",
            source=True,
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 1, plugin.CTR_SRC_DATA: 1},
            file_asserts={
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
            errored={plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "redbark_balances_2026.csv": [assert_file_does_not_exist()],
                "redbark_transactions_2026.csv": [assert_file_does_not_exist()],
            },
        )

    # A moved balance sweeps the transactions, but an unreadable year file is kept, not merged into, and counts an errored file while the balances commit
    def test_bank_local_corrupt_16(self):
        self._bank_run(
            "corrupt_16",
            source=True,
            rerun=False,
            errored={plugin.CTR_SRC_FILES: 1},
            file_asserts={
                "redbark_transactions_2026.csv": [assert_file_does_exist()],
                "__bank_transactions_current.csv": [assert_file_size(min_rows=0, max_rows=0)],
                "__bank_balances_current.csv": [assert_file_size(min_rows=3, max_rows=3)],
            },
        )

    # A live transactions list missing its status column is one source error writing no transactions, while the balances still commit
    def test_bank_local_corrupt_17(self):
        self._bank_run(
            "corrupt_17",
            source=True,
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "redbark_transactions_2026.csv": [assert_file_does_not_exist()],
                "__bank_balances_current.csv": [assert_file_size(min_rows=2, max_rows=2)],
            },
        )

    # A blank status triggers the accounts call, which fails, a source error leaving no linked account to check
    def test_bank_local_corrupt_18(self):
        self._bank_run(
            "corrupt_18",
            source=True,
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "redbark_balances_2026.csv": [assert_file_does_not_exist()],
            },
        )

    # A moved balance sweeps each account from its newest held date less the leeway: a held transaction is not added again and the new ones land
    def test_bank_local_partial_11(self):
        self._bank_run(
            "partial_11",
            standing=2,
            source=True,
            file_asserts={
                "redbark_transactions_2026.csv": [
                    assert_file_size(min_rows=3, max_rows=3),
                    assert_file_column_values("Source ID", ["t1", "t2", "t6"], sort_by=["Date"]),
                ],
                "__bank_transactions_current.csv": [assert_file_column_values("Account", ["One", "One", "Two"], sort_by=["Date"])],
            },
        )

    # A posting inside the leeway lands in the previous year's file, writing both years, and one before the window is not fetched
    def test_bank_local_partial_12(self):
        self._bank_run(
            "partial_12",
            standing=4,
            source=True,
            file_asserts={
                "redbark_transactions_2025.csv": [assert_file_size(min_rows=1, max_rows=1), assert_file_column_values("Source ID", ["t7"])],
                "redbark_transactions_2026.csv": [assert_file_size(min_rows=2, max_rows=2), assert_file_column_values("Source ID", ["t3", "t9"], sort_by=["Date"])],
                "__bank_transactions_current.csv": [assert_file_size(min_rows=3, max_rows=3)],
            },
        )

    # Blank statuses trigger the accounts call: a match is linked, two Redbark accounts on one key duplicate and none missing, each a source error, a linked
    # account Redbark no longer lists is marked missing, an unlisted Redbark account is appended linked below a row without a key, which is left untouched, and
    # every account id cell is filled or corrected to the id its institution and number derive
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

    # An id-less held transaction absorbs at most one live transaction of the same amount within three days, the nearest, by name across a replaced card number,
    # adopting its source id, and a transaction posted six days after it was made is matched on the day it was made, as history dates it, while a second identical
    # one, one four days away and a new one are kept
    def test_bank_local_partial_14(self):
        self._bank_run(
            "partial_14",
            standing=2,
            source=True,
            file_asserts={
                "redbark_transactions_2026.csv": [
                    assert_file_size(min_rows=7, max_rows=7),
                    assert_file_column_values("Source ID", ["l6", "l3", "l1", "l2", "l4", None, "l5"], sort_by=["Date", "Source ID"]),
                ],
                "__bank_transactions_current.csv": [assert_file_column_distinct("Transaction ID", 7)],
            },
        )

    # A first run with no files: an account backfills from its from date, a posting before it not fetched, and one with a blank from date takes everything within
    # seven years
    def test_bank_local_partial_17(self):
        self._bank_run(
            "partial_17",
            standing=4,
            source=True,
            file_asserts={
                "redbark_balances_2026.csv": [assert_file_size(min_rows=2, max_rows=2)],
                "redbark_transactions_2025.csv": [assert_file_column_values("Source ID", ["t1", "t2"], sort_by=["Date"])],
                "redbark_transactions_2026.csv": [assert_file_column_values("Source ID", ["t3"])],
            },
        )

    # A current balances file holding only its header has no readings, so every balance is stored
    def test_bank_local_partial_18(self):
        self._bank_run(
            "partial_18",
            source=True,
            file_asserts={
                "redbark_balances_2026.csv": [assert_file_size(min_rows=2, max_rows=2)],
                "__bank_balances_current.csv": [assert_file_size(min_rows=2, max_rows=2)],
            },
        )

    # Accounts, balances and transactions together: a history year file, a live posting held there without a source id, a pending one ignored, Redbark's codes
    # stored as codes with the placeholder merchant code blank, and every transaction id pinned to its account id, posted date, amount in cents, description and
    # ordinal
    def test_bank_local_replete_4(self):
        self._bank_run(
            "replete_4",
            standing=2,
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
                            "91ae10de62c15064b77e3b46e137bacc",
                        ],
                        sort_by=["Date"],
                    ),
                    assert_file_column_values("Split", ["0", "0", "0", "0", "0"]),
                ],
            },
        )

    # A dead Redbark id answers 404: the accounts are fetched again, the row's id replaced, and the retried query lands
    def test_bank_local_partial_19(self):
        self._bank_run(
            "partial_19",
            standing=2,
            source=True,
            file_asserts={
                "_sheet_bank_accounts.csv": [assert_file_column_values("Redbark Account ID", ["a1n"]), assert_file_column_values("Redbark Connection ID", ["c2"])],
                "redbark_transactions_2026.csv": [assert_file_column_values("Source ID", ["t1"])],
            },
        )

    # A rate limited transactions call is a source error merging nothing for that account, while the other account merges
    def test_bank_local_corrupt_19(self):
        self._bank_run(
            "corrupt_19",
            standing=2,
            source=True,
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "redbark_transactions_2026.csv": [assert_file_column_values("Source ID", ["t1"])],
            },
        )

    # The first due check of a day sweeps the transactions though no balance moved
    def test_bank_local_partial_20(self):
        self._bank_run(
            "partial_20",
            standing=2,
            source=True,
            file_asserts={
                "redbark_balances_2026.csv": [assert_file_size(min_rows=2, max_rows=2)],
                "redbark_transactions_2026.csv": [assert_file_column_values("Source ID", ["t1"])],
            },
        )

    # A changed accounts tab against the committed snapshot and state re-derives every balance and transaction in place, after which reruns are no-ops
    def test_bank_local_replete_2(self):
        self._bank_run(
            "replete_2",
            counters={plugin.CTR_SRC_FILES: {plugin.CTR_ACT_PROCESSED: 2}, plugin.CTR_SRC_DATA: {plugin.CTR_ACT_DELTA_ROWS: 2}},
            file_asserts={
                "__bank_balances_current.csv": [assert_file_size(min_rows=1, max_rows=1), assert_file_column_values("Account", ["Uno"])],
                "__bank_transactions_current.csv": [assert_file_size(min_rows=1, max_rows=1), assert_file_column_values("Account", ["Uno"])],
            },
        )

    # A usable accounts tab with no committed snapshot, as after an unusable one, re-derives every balance and commits its snapshot
    def test_bank_local_replete_3(self):
        self._bank_run(
            "replete_3",
            counters={plugin.CTR_SRC_FILES: {plugin.CTR_ACT_PROCESSED: 1}},
            file_asserts={
                "__bank_balances_current.csv": [assert_file_column_values("Account", ["One"]), assert_file_column_values("Account Institution", ["Bank A"])],
                "__bank_accounts_dimension.csv": [assert_file_does_exist()],
            },
        )

    # The balances tab holds every reading of the current and previous months and each active account's latest older one, sorted by account name then newest
    # first, a closed account dropping off, while the state keeps every reading
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

    # Review per year tab: unclassified or unvetted rows in a closed month are an error, only in the current month a warning, a vetted classified
    # year clean, and a stored vetted value read whatever its case and spacing
    def test_bank_local_partial_37(self):
        self._bank_run(
            "partial_37",
            standing=5,
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

    # A year with rows both before and in the open month raises a closed months error and an open month warning
    def test_bank_local_partial_37_split(self):
        self._bank_run(
            "partial_37",
            today="2026-02-15T12:00:00",
            standing=7,
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

    # Vetted typed on a linked account's rows: a tick is saved, a category change clears a tick left as it was but keeps one set with it, an unknown value is one
    # rejected record reverted by the rewrite, and a value is saved title cased whatever its case and spacing
    def test_bank_local_partial_40(self):
        self._bank_run(
            "partial_40",
            standing=1,
            sheet_downloads=1,
            errored={plugin.CTR_SRC_DATA: 1},
            file_asserts={
                "redbark_transactions_2025.csv": [
                    assert_file_column_values("Vetted", ["Yes", None, "Yes", None, "No"], sort_by=["Description"]),
                    assert_file_column_values("Category Manual", [None, "Clothing", "Clothing", None, None], sort_by=["Description"]),
                ],
                "__bank_logs.csv": [assert_file_column_values("Code", ["TRANSACTIONS_UNVETTED", "TRANSACTION_VETTED"], sort_by=["Code"])],
            },
        )

    # A forced reprocess re-derives every row: a vetted row whose category moves loses its tick, one no pattern matches any more is blanked and loses its tick, and
    # one held by a manual category keeps its tick while its derived category follows the classifier
    def test_bank_local_partial_41(self):
        self._bank_run(
            "partial_41",
            standing=2,
            rerun=False,
            force=True,
            errored={plugin.CTR_SRC_DATA: 1},
            file_asserts={
                "redbark_transactions_2025.csv": [
                    assert_file_column_values("Category Derived", [None] * 9 + ["Groceries", "Groceries"], sort_by=["Description"]),
                    assert_file_column_values("Vetted", [None] * 10 + ["Yes"], sort_by=["Description"]),
                ],
            },
        )

    # A classifier edit re-derives every row on the next run: a vetted row whose category moves loses its tick, a manual row keeps category and tick while its derived
    # category follows, an unmatched row is blanked and loses its tick, the snapshot is replaced, and each change is logged once in the run's month, the closed month
    # untouched, the rerun and reprocess moving nothing more
    def test_bank_local_partial_47(self):
        self._bank_run(
            "partial_47",
            standing=2,
            errored={plugin.CTR_SRC_DATA: 1},
            file_asserts={
                "redbark_transactions_2025.csv": [
                    assert_file_column_values("Category Derived", ["Restaurants", "Restaurants"] + [None] * 7 + ["Groceries"], sort_by=["Description"]),
                    assert_file_column_values("Vetted", [None, "Yes"] + [None] * 7 + ["Yes"], sort_by=["Description"]),
                ],
                "bank_reclassified_2026_01.csv": [
                    assert_file_column_values("Description", ["Cafe One", "Cafe Two", "Gone One"], sort_by=["Description"]),
                    assert_file_column_values("Source", ["classifier"] * 3, sort_by=["Description"]),
                    assert_file_column_values("Derived Before", ["Food"] * 3, sort_by=["Description"]),
                    assert_file_column_values("Derived After", ["Restaurants", "Restaurants", None], sort_by=["Description"]),
                    assert_file_column_values("Vetted After", [None, "Yes", None], sort_by=["Description"]),
                    assert_file_nones_per_col(include=r"File MD5"),
                ],
                "bank_reclassified_2025_12.csv": [assert_file_size(min_rows=1, max_rows=1)],
                "__bank_classifier.csv": [assert_file_column_values("Category", ["Groceries", "Food", "Restaurants"])],
                "__bank_logs.csv": [assert_file_column_values("Code", ["TRANSACTIONS_MOVED", "TRANSACTIONS_UNCLASSIFIED", "TRANSACTIONS_UNVETTED"], sort_by=["Code"])],
            },
        )

    # With the tab unchanged a standard run leaves a category no rule produces, as the release's first run does, and logs nothing
    def test_bank_local_partial_48(self):
        self._bank_run(
            "partial_48",
            standing=2,
            rerun=False,
            file_asserts={
                "redbark_transactions_2025.csv": [
                    assert_file_column_values("Category Derived", [None] * 4 + ["Legacy", "Groceries"], sort_by=["Description"]),
                    assert_file_column_values("Vetted", [None] * 4 + ["Yes", "Yes"], sort_by=["Description"]),
                ],
                "bank_reclassified_2026_01.csv": [assert_file_does_not_exist()],
            },
        )

    # With the tab unchanged a reprocess, as the release's second run, blanks the category no rule produces and clears its tick, logging the change
    def test_bank_local_partial_48_reprocess(self):
        self._bank_run(
            "partial_48",
            standing=2,
            rerun=False,
            force=True,
            errored={plugin.CTR_SRC_DATA: 1},
            file_asserts={
                "redbark_transactions_2025.csv": [
                    assert_file_column_values("Category Derived", [None] * 5 + ["Groceries"], sort_by=["Description"]),
                    assert_file_column_values("Vetted", [None] * 5 + ["Yes"], sort_by=["Description"]),
                ],
                "bank_reclassified_2026_01.csv": [
                    assert_file_column_values("Description", ["Old One"]),
                    assert_file_column_values("Derived Before", ["Legacy"]),
                    assert_file_column_values("Derived After", [None]),
                    assert_file_column_values("Vetted After", [None]),
                ],
            },
        )

    # A classifier edit with a pattern in two categories is held: rows keep the last applied tab's categories and ticks, a new row is classified by it, and the
    # snapshot is kept so the edit applies once the tab is fixed
    def test_bank_local_corrupt_33(self):
        self._bank_run(
            "corrupt_33",
            standing=2,
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 2, plugin.CTR_SRC_DATA: 1},
            file_asserts={
                "redbark_transactions_2025.csv": [
                    assert_file_column_values("Category Derived", ["Food"] + [None] * 3 + ["Food", "Groceries"], sort_by=["Description"]),
                    assert_file_column_values("Vetted", ["Yes"] + [None] * 4 + ["Yes"], sort_by=["Description"]),
                ],
                "__bank_classifier.csv": [assert_file_column_values("Category", ["Food", "Groceries"])],
                "__bank_logs.csv": [
                    assert_file_column_values(
                        "Code",
                        ["CLASSIFIER_HELD", "CLASSIFIER_PATTERN_CONFLICT", "TRANSACTIONS_MOVED", "TRANSACTIONS_UNCLASSIFIED", "TRANSACTIONS_UNVETTED"],
                        sort_by=["Code"],
                    )
                ],
            },
        )

    # A reprocess holds the same edit, re-deriving every row with the last applied tab
    def test_bank_local_corrupt_33_reprocess(self):
        self._bank_run(
            "corrupt_33",
            standing=2,
            rerun=False,
            force=True,
            errored={plugin.CTR_SRC_SOURCES: 2, plugin.CTR_SRC_DATA: 1},
            file_asserts={
                "redbark_transactions_2025.csv": [
                    assert_file_column_values("Category Derived", ["Food"] + [None] * 3 + ["Food", "Groceries"], sort_by=["Description"]),
                    assert_file_column_values("Vetted", ["Yes"] + [None] * 4 + ["Yes"], sort_by=["Description"]),
                ],
                "__bank_classifier.csv": [assert_file_column_values("Category", ["Food", "Groceries"])],
                "__bank_logs.csv": [
                    assert_file_column_values(
                        "Code",
                        ["CLASSIFIER_HELD", "CLASSIFIER_PATTERN_CONFLICT", "TRANSACTIONS_MOVED", "TRANSACTIONS_UNCLASSIFIED", "TRANSACTIONS_UNVETTED"],
                        sort_by=["Code"],
                    )
                ],
            },
        )

    # A bucket-only classifier edit clears no tick and logs nothing, the month totals regrouped under the new bucket
    def test_bank_local_partial_49(self):
        self._bank_run(
            "partial_49",
            standing=2,
            file_asserts={
                "redbark_transactions_2025.csv": [assert_file_column_values("Vetted", ["Yes"] + [None] * 6 + ["Yes"], sort_by=["Description"])],
                "bank_reclassified_2026_01.csv": [assert_file_does_not_exist()],
                "_sheet_bank_transactions.csv": [
                    assert_file_column_values("Category", ["Food", "Groceries", "Uncategorised"]),
                    assert_file_column_values("Bucket", ["Discretionary", "Living", "Unbucketed"]),
                ],
            },
        )

    # With the tab unchanged a normal run re-derives the files its edits changed: a ticked uncategorised row gains a category and loses the tick, an edited manual
    # description is reclassified, the untouched row keeps its category and tick, and each change is logged by its source
    def test_bank_local_partial_50(self):
        self._bank_run(
            "partial_50",
            standing=3,
            sheet_downloads=1,
            errored={plugin.CTR_SRC_DATA: 1},
            file_asserts={
                "redbark_transactions_2025.csv": [
                    assert_file_column_values("Category Derived", ["Food"] + [None] * 4 + ["Groceries"], sort_by=["Description"]),
                    assert_file_column_values("Vetted", ["Yes"] + [None] * 5, sort_by=["Description"]),
                ],
                "manual_transactions_2025.csv": [
                    assert_file_column_values("Description", ["Shop Three"]),
                    assert_file_column_values("Category Derived", ["Groceries"]),
                ],
                "bank_reclassified_2026_01.csv": [
                    assert_file_column_values("Source", ["classifier", "classifier", "sheet"], sort_by=["Source", "Description"]),
                    assert_file_column_values("Description", ["Shop Three", "Shop Two", "Shop Two"], sort_by=["Source", "Description"]),
                    assert_file_column_values("Vetted After", [None, None, "Yes"], sort_by=["Source", "Description"]),
                    assert_file_column_values("Derived After", ["Groceries", "Groceries", None], sort_by=["Source", "Description"]),
                ],
            },
        )

    # A manual category equal to the row's category keeps its tick and a different one left unticked clears it; a stale tab, its derived category from before a move,
    # cannot re-tick the row but can untick one, and only the edits are logged
    def test_bank_local_partial_51(self):
        self._bank_run(
            "partial_51",
            standing=2,
            sheet_downloads=1,
            file_asserts={
                "redbark_transactions_2025.csv": [
                    assert_file_column_values("Vetted", [None] * 4 + ["Yes", None, None, None], sort_by=["Description"]),
                    assert_file_column_values("Category Manual", [None] * 4 + ["Groceries", "Food", None, None], sort_by=["Description"]),
                ],
                "bank_reclassified_2026_01.csv": [
                    assert_file_column_values("Description", ["Shop A", "Shop B", "Shop D"], sort_by=["Description"]),
                    assert_file_column_values("Source", ["sheet"] * 3, sort_by=["Description"]),
                    assert_file_column_values("Vetted After", ["Yes", None, None], sort_by=["Description"]),
                ],
            },
        )

    # A failed drive sync leaves the run's changes unlogged with an error, the classifier edit still applied
    def test_bank_local_corrupt_34(self):
        self._bank_run(
            "corrupt_34",
            standing=2,
            rerun=False,
            drive_failed=True,
            errored={plugin.CTR_SRC_SOURCES: 2, plugin.CTR_SRC_DATA: 1},
            file_asserts={
                "redbark_transactions_2025.csv": [assert_file_column_values("Vetted", [None, "Yes"] + [None] * 7 + ["Yes"], sort_by=["Description"])],
                "bank_reclassified_2026_01.csv": [assert_file_does_not_exist()],
                "__bank_logs.csv": [assert_file_column_values("Code", ["CHANGES_UNLOGGED", "TRANSACTIONS_MOVED", "TRANSACTIONS_UNCLASSIFIED", "TRANSACTIONS_UNVETTED"], sort_by=["Code"])],
            },
        )

    # A replaced card shares its name with the closed card it replaced, both holding transactions on one date without error
    def test_bank_local_partial_38(self):
        self._bank_run(
            "partial_38",
            file_asserts={
                "__bank_transactions_current.csv": [assert_file_size(min_rows=2, max_rows=2), assert_file_column_distinct("Account ID", 2)],
                "__bank_logs.csv": [assert_file_size(min_rows=0, max_rows=0)],
            },
        )

    # Two open cards sharing a name both holding transactions on one date are a source error
    def test_bank_local_corrupt_31(self):
        self._bank_run(
            "corrupt_31",
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "__bank_logs.csv": [assert_file_column_values("Code", ["ACCOUNT_NAME_SHARED"])],
            },
        )

    # A transaction held on both a closed card and the card replacing it under one name, matched on date, cents and description whatever its case and spacing,
    # is one standing warning, while the same purchase on another day is not
    def test_bank_local_partial_39(self):
        self._bank_run(
            "partial_39",
            standing=1,
            file_asserts={
                "__bank_transactions_current.csv": [assert_file_size(min_rows=3, max_rows=3)],
                "__bank_logs.csv": [
                    assert_file_column_values("Code", ["TRANSACTION_TWO_ACCOUNTS"]),
                    assert_file_column_values("Tab", ["Transactions_2026"]),
                ],
            },
        )

    # An accounts tab holding only its header is filled from Redbark: every account appended linked with its ids, a credit card as a liability, and its balances
    # stored on the same run
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

    # Two otherwise identical linked transactions, the first given a category manual: the rewrite keeps each at its place in the file, so the edited one keeps its
    # own id
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

    # A swept transactions response: a merchant code short of four digits is padded, and two transactions sharing a Redbark id are both rejected
    def test_bank_local_partial_44(self):
        self._bank_run(
            "partial_44",
            standing=2,
            source=True,
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "redbark_transactions_2026.csv": [assert_file_column_values("Source ID", ["t1"]), assert_file_column_values("Merchant Code", ["0812"], raw=True)],
                "__bank_logs.csv": [assert_file_column_values("Code", ["TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED_CURRENT", "TRANSACTION_RESPONSE"], sort_by=["Code"])],
            },
        )

    # Two identical history transactions stay two transactions told apart by their ordinal, each with its own pinned id
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

    # Split parts are derived on read: -1000, -500, -500 is one whole transaction and one split in two parts sharing an id
    def test_bank_local_partial_15(self):
        self._bank_run(
            "partial_15",
            standing=2,
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

    # An unreadable year file is kept and counts an errored file, its year left as committed while another year commits
    def test_bank_local_corrupt_15(self):
        self._bank_run(
            "corrupt_15",
            standing=2,
            rerun=False,
            errored={plugin.CTR_SRC_FILES: 1},
            file_asserts={
                "redbark_transactions_2026.csv": [assert_file_does_exist()],
                "__bank_transactions_current.csv": [assert_file_size(min_rows=1, max_rows=1), assert_file_dates(start_date="2025-12-03", end_date="2025-12-03")],
            },
        )

    # Manual balances typed on the balances tab: a value set on a carried reading makes it real, a changed one is saved, a cleared one deleted (a year left with none
    # emptied rather than removed, so the empty file reaches Drive), and a new row with a blank date and time lands at the end of today, the carried readings
    # following and a real reading winning at the same moment
    def test_bank_local_partial_21(self):
        self._bank_run(
            "partial_21",
            sheet_downloads=1,
            file_asserts={
                "manual_balances_2026.csv": [
                    assert_file_column_values("Balance Manual", ["101.0", "105.0", "110.0"], sort_by=["Date"]),
                    assert_file_column_values("Time", ["23:59:59", "09:00:00", "23:59:59"], sort_by=["Date"]),
                ],
                "manual_balances_2025.csv": [assert_file_size(min_rows=0, max_rows=0), assert_file_columns(list(BALANCES_SCHEMA))],
                "__bank_balances_current.csv": [
                    assert_file_size(min_rows=6, max_rows=6),
                    assert_file_column_values("Balance", ["101.0", "101.0", "10.0", "105.0", "12.0", "110.0"], sort_by=["Date", "Time", "Account"]),
                ],
            },
        )

    # Rejected balance edits each count a data error and are reverted by the rewrite: a value on a linked row, an unknown account, a future date and an unparsed value
    def test_bank_local_corrupt_20(self):
        self._bank_run(
            "corrupt_20",
            sheet_downloads=1,
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 4},
            file_asserts={
                "manual_balances_2026.csv": [assert_file_size(min_rows=1, max_rows=1)],
                "_sheet_bank_balances.csv": [
                    assert_file_column_values("Account", ["Cash", "Cash", "One"]),
                    assert_file_column_values("Balance Manual", ["100.0", "100.0", None]),
                ],
                "__bank_logs.csv": [assert_file_column_values("Code", ["ACCOUNT_LINKED", "ACCOUNT_NOT_MANUAL", "DATE_FUTURE", "VALUE_UNPARSED"], sort_by=["Code"])],
            },
        )

    # Manual transactions typed on the year tabs: an edit moving its amount split, a deletion, a new row, a date moved across years and an edited placeholder each
    # land in the right manual file, and the placeholders roll to exactly one per manual account this month, the stale one gone
    def test_bank_local_partial_22(self):
        self._bank_run(
            "partial_22",
            standing=2,
            sheet_downloads=1,
            file_asserts={
                "manual_transactions_2026.csv": [
                    assert_file_size(min_rows=6, max_rows=6),
                    assert_file_column_values("Description", ["Tip", "Null Transaction", "Null Transaction", "Snack", "Lunch", "Dinner"], sort_by=["Date", "Amount", "Account"]),
                    assert_file_column_values("Amount Split", ["-3.0", "0.0", "0.0", "-5.0", "-12.0", "-30.0"], sort_by=["Date", "Amount", "Account"]),
                ],
                "manual_transactions_2025.csv": [assert_file_size(min_rows=0, max_rows=0), assert_file_columns(list(TRANSACTIONS_SCHEMA))],
                "__bank_transactions_current.csv": [
                    assert_file_size(min_rows=5, max_rows=5),
                    assert_file_column_values("Description", ["Tip", "Snack", "Lunch", "Coffee", "Dinner"], sort_by=["Date"]),
                ],
                "_sheet_bank_transactions_2026.csv": [assert_file_size(min_rows=7, max_rows=7)],
            },
        )

    # Rejected transaction edits each count a data error and are reverted by the rewrite: a linked row's description, a new row for a linked account and a split not
    # summing to its amount
    def test_bank_local_corrupt_21(self):
        self._bank_run(
            "corrupt_21",
            standing=2,
            sheet_downloads=1,
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 3},
            file_asserts={
                "redbark_transactions_2026.csv": [assert_file_column_values("Description", ["Coffee", "Fee"], sort_by=["Date"])],
                "_sheet_bank_transactions_2026.csv": [assert_file_size(min_rows=2, max_rows=2)],
                "__bank_logs.csv": [
                    assert_file_column_values("Code", ["ACCOUNT_LINKED", "ACCOUNT_LINKED", "SPLIT_INVALID", "TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED_CURRENT"], sort_by=["Code"])
                ],
            },
        )

    # A manual transaction moved into a year whose manual file is unreadable, and a new row dated in that year, are each rejected as a data error, the moved one kept
    # where it was and the unreadable file counting an errored file
    def test_bank_local_corrupt_32(self):
        self._bank_run(
            "corrupt_32",
            standing=2,
            sheet_downloads=1,
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 2, plugin.CTR_SRC_FILES: 1},
            file_asserts={
                "manual_transactions_2026.csv": [assert_file_column_values("Description", ["Null Transaction", "Lunch"], sort_by=["Date"])],
                "manual_transactions_2025.csv": [assert_file_does_exist()],
                "__bank_logs.csv": [assert_file_column_values("Code", ["FILE_UNREADABLE", "FILE_UNREADABLE", "TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED_CURRENT"], sort_by=["Code"])],
            },
        )

    # On linked rows a category manual and a valid split are kept, the split saved as contiguous parts sharing one id, the bucket following the resolved category
    def test_bank_local_partial_23(self):
        self._bank_run(
            "partial_23",
            standing=1,
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

    # Classification by the longest literal pattern, then merchant code, then bank code: nested patterns across categories, padded whitespace, a metacharacter
    # matched literally, a merchant code over a bank code and an unmapped income code left blank; the changed tab re-derives every row, the history's own category
    # included, clearing the tick of the vetted row it moves, while a category manual still wins and keeps its tick
    def test_bank_local_partial_24(self):
        self._bank_run(
            "partial_24",
            standing=2,
            errored={plugin.CTR_SRC_DATA: 1},
            file_asserts={
                "redbark_transactions_2026.csv": [
                    assert_file_column_values(
                        "Category Derived",
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

    # Classifier standing errors, one source error each: a bank code not a CDR code, a merchant code not four digits, two code rows for one category, and two patterns
    # of equal length from different categories matching one description, which takes neither; the edit is held, and with no tab yet applied nothing is classified
    def test_bank_local_corrupt_22(self):
        self._bank_run(
            "corrupt_22",
            standing=2,
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 5},
            file_asserts={
                "redbark_transactions_2026.csv": [assert_file_column_values("Category Derived", [None] * 7)],
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

    # The plugin's own uploads read back as no edit: every run sees the tabs moved and compares them, an id, a description starting with an equals sign or holding a
    # comma and a merchant code with a leading zero round trip, and the rerun uploads nothing
    def test_bank_local_partial_25(self):
        self._bank_run(
            "partial_25",
            standing=4,
            sheet_downloads=99,
            file_asserts={
                "_sheet_bank_balances.csv": [assert_file_does_exist()],
                "_sheet_bank_transactions_2026.csv": [assert_file_size(min_rows=7, max_rows=7)],
                "_sheet_bank_transactions_2025.csv": [assert_file_size(min_rows=1, max_rows=1)],
                "_sheet_bank_transactions.csv": [assert_file_column_distinct("End of Month", 1)],
            },
        )

    # A tab edited between the read and the upload is not overwritten: its upload and every later one are skipped
    def test_bank_local_partial_26(self):
        self._bank_run(
            "partial_26",
            standing=2,
            sheet_downloads=0,
            moved_tabs=("Balances",),
            rerun=False,
            file_asserts={
                "_sheet_bank_balances.csv": [assert_file_column_values("Balance Linked", ["10.0"])],
                "_sheet_bank_transactions_2026.csv": [assert_file_does_not_exist()],
                "__bank_balances_current.csv": [assert_file_size(min_rows=1, max_rows=1)],
            },
        )

    # A tab read back with its numbers displayed differently, as the sheet shows 10.0 as 10, is the same tab: the guard compares typed values and the upload goes ahead
    def test_bank_local_partial_35(self):
        self._bank_run(
            "partial_35",
            standing=2,
            sheet_downloads=0,
            restyled_tabs=("Balances",),
            rerun=False,
            file_asserts={
                "_sheet_bank_balances.csv": [assert_file_column_values("Balance Linked", ["12.0"])],
                "_sheet_bank_transactions_2026.csv": [assert_file_size(min_rows=1, max_rows=1)],
            },
        )

    # Forced reprocessing dedupes every transactions file by source id, each removal a data error: one in two files keeps the earlier, while a sourced transaction
    # beside an id-less one of the same amount within three days, as genuine repeats are, split parts sharing a source id and identical id-less transactions all stay
    def test_bank_local_partial_27(self):
        self._bank_run(
            "partial_27",
            standing=4,
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

    # A sweep on a normal run writes a transaction Redbark now dates inside the window whose source id an unchanged older year file holds: the dedupe compares every
    # file, removing it from the changed one as a data error
    def test_bank_local_partial_45(self):
        self._bank_run(
            "partial_45",
            standing=4,
            source=True,
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 1},
            file_asserts={
                "redbark_transactions_2025.csv": [assert_file_column_values("Source ID", ["t1"])],
                "redbark_transactions_2026.csv": [assert_file_column_values("Source ID", ["t9"])],
                "__bank_transactions_current.csv": [assert_file_size(min_rows=2, max_rows=2)],
                "__bank_logs.csv": [
                    assert_file_column_values(
                        "Code",
                        ["DEDUPE_REMOVED", "TRANSACTIONS_UNCLASSIFIED", "TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED", "TRANSACTIONS_UNVETTED_CURRENT"],
                        sort_by=["Code"],
                    )
                ],
            },
        )

    # Month end totals on the Transactions tab, a row per month for each category with transactions: labelled by the next month's first, the current month and quiet months
    # left out, refunds netting, budgeted rows first then by bucket and category
    def test_bank_local_partial_28(self):
        self._bank_run(
            "partial_28",
            standing=2,
            file_asserts={
                "_sheet_bank_transactions.csv": [
                    assert_file_columns(["End of Month", "Budgeted", "Bucket", "Category", "Total"]),
                    assert_file_column_values("End of Month", ["2026-01-01"] * 4 + ["2025-11-01"]),
                    assert_file_column_values("Budgeted", ["Yes", "Yes", "No", "No", "Yes"]),
                    assert_file_column_values("Bucket", ["Discretionary", "Living", "Transfers", "Unbucketed", "Living"]),
                    assert_file_column_values("Category", ["Restaurants", "Groceries", "Transfer", "Uncategorised", "Groceries"]),
                    assert_file_column_values("Total", ["50.0", "-20.0", "200.0", "1.0", "100.0"]),
                ],
            },
        )

    # The logs tab lists this run's standing problems and the last thirty days of rejected records, dropping older ones
    def test_bank_local_partial_29(self):
        self._bank_run(
            "partial_29",
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "_sheet_bank_logs.csv": [
                    assert_file_columns(["Date", "Time", "Kind", "Counter", "Tab", "Key", "Code", "Detail"]),
                    assert_file_column_values("Code", ["ACCOUNT_UNMAPPED", "VALUE_UNPARSED"]),
                ],
            },
        )

    # An account type outside the two and a status outside the vocabulary each count a source error, the type read as an asset
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

    # A balance whose freshness is not fresh is a standing source error, the reading still stored
    def test_bank_local_corrupt_24(self):
        self._bank_run(
            "corrupt_24",
            source=True,
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "redbark_balances_2026.csv": [assert_file_size(min_rows=2, max_rows=2)],
                "__bank_logs.csv": [assert_file_column_values("Code", ["BALANCE_STALE"])],
            },
        )

    # A dead Redbark id with no replacement on the accounts call is a standing source error, merging nothing for it
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

    # Manual balance checks: a reading before its account's from date and two entries for one moment are rejected, while a liability above zero and a ten-fold
    # jump are kept as suspect, one data error per record
    def test_bank_local_corrupt_26(self):
        self._bank_run(
            "corrupt_26",
            sheet_downloads=1,
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 5},
            file_asserts={
                "manual_balances_2026.csv": [assert_file_column_values("Balance Manual", ["-50.0", "100.0", "20.0", "5000.0"], sort_by=["Date", "Account"])],
                "__bank_logs.csv": [assert_file_column_values("Code", ["BALANCE_DUPLICATE", "BALANCE_DUPLICATE", "BALANCE_JUMP", "BALANCE_SIGN", "DATE_BEFORE_FROM"], sort_by=["Code"])],
            },
        )

    # Manual transaction checks, each rejected: an unparsed amount, an unknown account, a future date, a date before the account's from date, more than two decimals,
    # a zero amount and a blank description; while one identical to another and an unknown category manual are kept as suspect
    def test_bank_local_corrupt_27(self):
        self._bank_run(
            "corrupt_27",
            standing=2,
            sheet_downloads=1,
            rerun=False,
            errored={plugin.CTR_SRC_DATA: 9, plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "manual_transactions_2026.csv": [assert_file_column_values("Description", ["Null Transaction", "Lunch", "Lunch", "Treat"], sort_by=["Date", "Description"])],
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
                            "TRANSACTIONS_UNCLASSIFIED_CURRENT",
                            "TRANSACTIONS_UNVETTED_CURRENT",
                            "TRANSACTION_DECIMALS",
                            "TRANSACTION_DESCRIPTION",
                            "TRANSACTION_ZERO",
                            "VALUE_UNPARSED",
                        ],
                        sort_by=["Code"],
                    )
                ],
            },
        )

    # A held transaction inside the window that Redbark no longer lists is kept and counted as suspect, while one posted inside the window but made before it, so
    # not listed, is not
    def test_bank_local_corrupt_28(self):
        self._bank_run(
            "corrupt_28",
            standing=4,
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

    # Classifier standing errors, one source error per code: a blank category, a category in two buckets, a blank budgeted, categories differing only in case, a
    # short pattern, a code list on a pattern row, one pattern in two categories, a pattern matching over the share, and a category in use the tab lacks, holding the edit
    def test_bank_local_corrupt_29(self):
        self._bank_run(
            "corrupt_29",
            standing=2,
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 10},
            file_asserts={
                "__bank_logs.csv": [assert_file_column_distinct("Code", 12)],
            },
        )

    # A classifier tab with a misplaced column is unusable, a source error classifying nothing
    def test_bank_local_corrupt_30(self):
        self._bank_run(
            "corrupt_30",
            standing=2,
            rerun=False,
            errored={plugin.CTR_SRC_SOURCES: 1},
            file_asserts={
                "redbark_transactions_2026.csv": [assert_file_column_values("Category Derived", [None])],
                "__bank_logs.csv": [assert_file_column_values("Code", ["TAB_UNUSABLE", "TRANSACTIONS_UNCLASSIFIED_CURRENT", "TRANSACTIONS_UNVETTED_CURRENT"], sort_by=["Code"])],
            },
        )

    # A category manual typed on the tab is merged before the sweep, so the Redbark rewrite of the year file keeps it
    def test_bank_local_partial_30(self):
        self._bank_run(
            "partial_30",
            standing=2,
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

    # A tab sorted by hand is not an edit: rows are matched on their id, never their position, so no file changes and the tab is rewritten in order
    def test_bank_local_partial_31(self):
        self._bank_run(
            "partial_31",
            standing=2,
            sheet_downloads=1,
            file_asserts={
                "manual_transactions_2026.csv": [assert_file_size(min_rows=4, max_rows=4)],
                "_sheet_bank_transactions_2026.csv": [assert_file_column_values("Description", ["Coffee", "Fuel", "Lunch", "Null Transaction", "Null Transaction"])],
            },
        )

    # An accounts tab edited after the read is not written: the cells the call found are left for the next run, while this run still checks the account
    def test_bank_local_partial_32(self):
        self._bank_run(
            "partial_32",
            source=True,
            sheet_downloads=0,
            moved_tabs=("Accounts",),
            rerun=False,
            file_asserts={
                "_sheet_bank_accounts.csv": [assert_file_column_values("Status", ["Linked", None])],
                "redbark_balances_2026.csv": [assert_file_size(min_rows=2, max_rows=2)],
            },
        )

    # No accounts tab: the accounts are fetched as before and every Redbark account is checked under its own name, without error
    def test_bank_local_partial_33(self):
        self._bank_run(
            "partial_33",
            standing=2,
            source=True,
            file_asserts={
                "__bank_balances_current.csv": [assert_file_column_values("Account", ["Raw One", "Raw Two"], sort_by=["Balance"])],
                "redbark_transactions_2026.csv": [assert_file_column_values("Source ID", ["t1"])],
            },
        )

    # Unsplitting: one copy deleted and the other's amount split set back to the amount restores one whole transaction
    def test_bank_local_partial_34(self):
        self._bank_run(
            "partial_34",
            sheet_downloads=1,
            file_asserts={
                "redbark_transactions_2026.csv": [assert_file_size(min_rows=1, max_rows=1), assert_file_column_values("Amount Split", ["-1000.0"])],
                "__bank_transactions_current.csv": [assert_file_column_values("Split", ["0"])],
            },
        )

    # Release's balances and transactions year files as the test data, never downloaded so every run starts from them, one deleted from the preview drive and
    # uploaded back, the release sheet's input tabs cached in place of the preview sheet's, and the live Redbark responses of the refresh replayed offline at its
    # pinned clock: the due balance check and transaction sweep land the live readings and postings exactly as the refresh's online run did, the changed files
    # upload to the preview drive, the cached tabs raise no error, and the tabs, an empty logs tab included, upload to the preview sheet
    @pytest.mark.xfail(strict=True, reason="production data cleanup")
    def test_bank_preview_replete_1(self):
        fixture = _load_fixture("preview", "bank", "replete_1")
        drive_delete(REPOS_BANK._scopes["preview"]["drive_folder"], "redbark_balances_2019.csv")
        bank_api_offline("replete_1", "preview")
        self.run_plugin(
            "bank",
            plugin.RepoScope.PREVIEW,
            "replete_1",
            log_level="info",
            disable_sheet_downloads=True,
            disable_database_downloads=True,
            disable_drive_downloads=True,
            disable_source_downloads=False,
            disable_sheet_uploads=False,
            disable_database_uploads=True,
            disable_drive_uploads=False,
            enable_rerun=True,
            force_reprocessing=False,
            force_downloads=False,
            counter_asserts=merge_asserts(
                ASSERT_RUN,
                {
                    "counter_at_least": {
                        plugin.CTR_SRC_SOURCES: {
                            plugin.CTR_ACT_UPLOADED: 1,
                            plugin.CTR_ACT_DOWNLOADED: 2,
                        },
                    },
                    "counter_equals": {
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
                "__bank_balances_current.csv": [
                    assert_file_size(),
                    assert_file_dates(end_date=fixture["end_date"], descending=False),
                    assert_file_nones_per_row(exclude=r"Balance Manual|Balance Linked|Account Institution|Account Number|Account Type"),
                ],
                "_sheet_bank_balances.csv": [
                    assert_file_size(),
                    assert_file_columns(list(BALANCES_SCHEMA)),
                ],
                "_sheet_bank_logs.csv": [
                    assert_file_size(min_rows=0, max_rows=0),
                    assert_file_columns(list(LOG_SCHEMA)),
                ],
                "__bank_transactions_current.csv": [
                    assert_file_size(min_rows=fixture["transactions_rows_delta"], max_rows=fixture["transactions_rows_delta"]),
                    assert_file_dates(end_date=fixture["transactions_end_date"], descending=False),
                    assert_file_column_distinct("Transaction ID", fixture["transactions_ids"]),
                ],
            },
        )

    # Balances and transactions current state from the release data repo, live balances and transactions downloaded from the source and the release sheet read, no
    # remote data repo uploads: both states gain the live data, the run and the reprocess commit identical states, and the real accounts and classifier tabs raise
    # no error
    @pytest.mark.xfail(strict=True, reason="production data cleanup")
    def test_bank_release_replete_1(self):
        fixture = _load_fixture("release", "bank", "replete_1")
        self.run_plugin(
            "bank",
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
                        plugin.CTR_SRC_DATA: {
                            plugin.CTR_ACT_DELTA_ROWS: fixture["rows_delta"],
                        },
                    },
                },
            ),
            file_asserts={
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
        self.assertEqual(DownloadResult(DownloadStatus.DOWNLOADED, download.file_paths), forced)
        plugin.config.force_downloads = False
        data_df = _sheet_read(download)
        self.assertEqual(data_str.format("Float64"), test.dataframe_to_str(data_df))
        self.assertEqual(24, len(data_df))
        data_df = _sheet_read(download, schema={"Port Quantity": pl.Utf8})
        self.assertEqual(data_str.format(test.dataframe_type_to_str(pl.Utf8)), test.dataframe_to_str(data_df))
        self.assertEqual(24, len(data_df))

        plugin.config.force_downloads = True
        batch = test.sheet_download(data_key, "Index_weights", ["Indexes", "Absent"], 2, schema={"Exchange Symbol": pl.Utf8, "Unit Price": pl.Float64})
        plugin.config.force_downloads = False
        self.assertEqual(DownloadStatus.DOWNLOADED, batch.file_status)
        self.assertEqual(2, len(batch.file_paths))
        self.assertEqual(24, len(test.csv_read(batch.file_paths[0])))
        self.assertEqual(0, len(test.csv_read(batch.file_paths[1])))
        self.assertEqual(DownloadStatus.CACHED, test.sheet_download(data_key, "Index_weights", ["Indexes", "Absent"], 2).file_status)

    def test_bank_flag(self):
        values = ["Yes", " yes ", "YES", "No", "no\t", " NO", "y", "", None, "true", "Yes No"]
        self.assertEqual(
            ["Yes", "Yes", "Yes", "No", "No", "No", None, None, None, None, None], pl.DataFrame({"Value": values}, schema={"Value": pl.Utf8}).select(bank_flag("Value"))["Value"].to_list()
        )

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
        self.assertTrue(isfile(join(test.local_cache, "_sheet_format_tab.csv")))
        test.sheet_upload(data_df, None, "Format", sheet_name="Tab", dropdown_columns={"Note": ["Yes", "No"], "Amount": [], "Amount Manual": ["Yes", ""]})
        with open(join(test.local_cache, "_sheet_format_tab_format.json")) as format_file:
            self.assertEqual({"raw": [], "formulas": {}, "dropdowns": {"Note": ["Yes", "No"]}, "highlights": []}, json.load(format_file))
        self.assertEqual(7, test.get_counter(plugin.CTR_SRC_EGRESS, plugin.CTR_ACT_ERRORED))

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
        moved_tabs=(),
        restyled_tabs=(),
        rerun=True,
        force=False,
        errored=None,
        standing=0,
        counters=None,
        file_asserts=None,
        custom_asserts=None,
        drive_failed=False,
    ):
        bank_api_offline(test_name)
        if sheet_downloads is not None:
            sheet_download_offline(sheet_downloads, moved_tabs, restyled_tabs)
        if drive_failed:

            def _drive_synchronise(self, *_args, **_kwargs):
                self.add_counter(plugin.CTR_SRC_SOURCES, plugin.CTR_ACT_ERRORED)
                return {}

            mock.patch.object(Plugin, "drive_synchronise", _drive_synchronise).start()
        self.run_plugin(
            "bank",
            plugin.RepoScope.LOCAL,
            test_name,
            log_level="info",
            disable_sheet_downloads=True,
            disable_database_downloads=True,
            disable_drive_downloads=not drive_failed,
            disable_source_downloads=not source,
            disable_sheet_uploads=True,
            disable_database_uploads=True,
            disable_drive_uploads=True,
            enable_rerun=rerun,
            force_reprocessing=force,
            force_downloads=False,
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
                    if not isfile(file_path) and expanded_filename.endswith(".csv"):
                        pass_match = re.search(r"(_\d_(run|rerun|reprocess))\.csv$", expanded_filename)
                        if pass_match:
                            pass_suffix = pass_match.group(1)
                            base_stem = expanded_filename[:-4][: -len(pass_suffix)]
                            versioned = sorted(glob.glob(join(plugin_module.local_cache, f"{base_stem}_v*{pass_suffix}.csv")))
                        else:
                            versioned = sorted(glob.glob(join(plugin_module.local_cache, f"{expanded_filename[:-4]}_v*.csv")))
                        if versioned:
                            file_path = versioned[-1]
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


def sheet_download_offline(downloads=1, moved_tabs=(), restyled_tabs=()):
    served = {"lists": 0}

    def _sheet_download(self, drive_key, workbook_name, sheet_name=None, *_args, **_kwargs):
        sheet_names = sheet_name if isinstance(sheet_name, list) else [sheet_name]
        file_paths = [self._sheet_cache_path((workbook_name if name is None else f"{workbook_name}_{name}").lower()) or "" for name in sheet_names]
        if isinstance(sheet_name, list):
            served["lists"] += 1
            status = DownloadStatus.DOWNLOADED if served["lists"] <= downloads else DownloadStatus.CACHED
            return DownloadResult(status if any(file_paths) else DownloadStatus.FAILED, file_paths if any(file_paths) else [])
        if not file_paths[0]:
            return DownloadResult(DownloadStatus.FAILED, [])
        if sheet_name in moved_tabs:
            moved_path = file_paths[0].removesuffix(".csv") + "_moved.csv"
            pl.concat([pl.read_csv(file_paths[0], infer_schema=False), pl.read_csv(file_paths[0], infer_schema=False).head(1)]).write_csv(moved_path)
            return DownloadResult(DownloadStatus.DOWNLOADED, [moved_path])
        if sheet_name in restyled_tabs:
            restyled_path = file_paths[0].removesuffix(".csv") + "_restyled.csv"
            pl.read_csv(file_paths[0], infer_schema=False).with_columns(pl.all().str.replace(r"^(-?\d+)\.0$", "$1")).write_csv(restyled_path)
            return DownloadResult(DownloadStatus.DOWNLOADED, [restyled_path])
        return DownloadResult(DownloadStatus.CACHED, file_paths)

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
                "cache_dir=../../../../target/.pytest_cache",
                __file__,
            ]
        )
    )
