import sys
from os.path import dirname

sys.path.insert(0, dirname(__file__))

import contextlib
import copy
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
import unittest
from collections.abc import Iterable
from datetime import date as date_type
from os.path import abspath, basename, dirname, isdir, isfile, join, realpath

import csv_diff  # type: ignore
import google.oauth2.service_account
import polars as pl
import pytest
import tomllib
from googleapiclient.discovery import build

sys.path.append('../../../main/python')

from wrangle import main as wrangle_main
from wrangle import plugin
from wrangle.plugin import DownloadResult, DownloadStatus, Plugin, database
from wrangle.plugin.balances import REPOS_BALANCES
from wrangle.plugin.config import get_file
from wrangle.plugin.counters import *
from wrangle.plugin.counters import CTR_TZ
from wrangle.plugin.currency import COLUMNS as CURRENCY_COLUMNS
from wrangle.plugin.currency import REPOS_CURRENCY
from wrangle.plugin.equity import DIMENSIONS_STATE, PORTFOLIO_TICKERS_ACTIVE, PORTFOLIO_TICKERS_MANUAL, PORTFOLIO_TICKERS_NODATA, REPOS_EQUITY, STOCK
from wrangle.plugin.interest import COLUMNS as INTEREST_COLUMNS
from wrangle.plugin.interest import REPOS_INTEREST
from wrangle.plugin.logger import dataframe_print, print_log
from wrangle.server.server import CHART_SPEC, TEMPLATE, THEMES, WEB_ROOT_DIR

########################################################################################################################
# NOTES:
#   - Include in test runner templates for realtime, unbuffered output: PYTHONUNBUFFERED=1;JB_DISABLE_BUFFERING=1
########################################################################################################################


pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning:multiprocessing")

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))


# noinspection PyMethodMayBeStatic
class WrangleTest(unittest.TestCase):

    ########################################################################################################################
    # Balances
    ########################################################################################################################

    # No current data, no new data, no remote source data downloads, no remote data repo downloads or uploads
    def test_balances_local_blank_1(self):
        fixture = _load_fixture("local", "balances", "blank_1")
        self.run_plugin("balances", plugin.RepoScope.LOCAL, "blank_1", log_level="info",
                        disable_sheet_downloads=True, disable_database_downloads=True, disable_drive_downloads=True, disable_source_downloads=True,
                        disable_sheet_uploads=True, disable_database_uploads=True, disable_drive_uploads=True,
                        enable_rerun=False, force_reprocessing=False, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_ERRORED: fixture["expected_errors"],
                                },
                            },
                        }),
                        file_asserts={
                            "__balances_current.csv": [
                                assert_file_does_not_exist(),
                            ],
                        })

    # No current data, corrupt data, no remote source data downloads, no remote data repo downloads or uploads
    @pytest.mark.skip(reason="requires update")
    def test_balances_local_corrupt_1(self):
        fixture = _load_fixture("local", "balances", "corrupt_1")
        self.run_plugin("balances", plugin.RepoScope.LOCAL, "corrupt_1", log_level="fatal",
                        disable_sheet_downloads=True, disable_database_downloads=True, disable_drive_downloads=True, disable_source_downloads=True,
                        disable_sheet_uploads=True, disable_database_uploads=True, disable_drive_uploads=True,
                        enable_rerun=False, force_reprocessing=True, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_ERRORED: fixture["expected_errors"],
                                },
                            },
                        }),
                        file_asserts={
                            "__balances_current.csv": [
                                assert_file_does_not_exist(),
                            ],
                        })

    # Lots of current data, a specific amount of new data, no remote source data downloads, downloads and uploads from and to preview data repo
    @pytest.mark.skip(reason="requires update")
    def test_balances_preview_replete_1(self):
        drive_delete(REPOS_BALANCES._scopes["preview"]["drive_folder"], "rba_fx_1987-1990.xls")
        self.run_plugin("balances", plugin.RepoScope.PREVIEW, "replete_1", log_level="info",
                        disable_sheet_downloads=True, disable_database_downloads=True, disable_drive_downloads=False, disable_source_downloads=True,
                        disable_sheet_uploads=False, disable_database_uploads=True, disable_drive_uploads=False,
                        enable_rerun=True, force_reprocessing=False, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
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
                        }),
                        custom_asserts=[
                            assert_custom_rows_delta(equals=14)
                        ],
                        file_asserts={
                            "__balances_current.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="1983-12-12", end_date="2024-10-14", contiguous="days"),
                                assert_file_nones_per_row(),
                                assert_file_zeroes_per_col(exclude=r"Delta"),
                            ],
                            "_sheet_rates_balances.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="1983-12-12", end_date="2024-10-14", contiguous="days", descending=True),
                                assert_file_nones_per_row(),
                                assert_file_zeroes_per_row(),
                            ],
                            "_database_balances.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="1983-12-12", end_date="2024-10-14", contiguous="days"),
                                assert_file_nones_per_row(),
                                assert_file_zeroes_per_col(exclude=r"type=delta"),
                            ],
                        })

    # Lots of current data, a lot of live new data, downloads from remote sources, downloads from release data repo, no remote data repo uploads
    @pytest.mark.skip(reason="requires update")
    def test_balances_release_replete_1(self):
        self.run_plugin("balances", plugin.RepoScope.RELEASE, "replete_1", log_level="info",
                        disable_sheet_downloads=False, disable_database_downloads=False, disable_drive_downloads=False, disable_source_downloads=False,
                        disable_sheet_uploads=True, disable_database_uploads=True, disable_drive_uploads=True,
                        enable_rerun=True, force_reprocessing=False, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_DATA: {
                                    plugin.CTR_ACT_PREVIOUS_COLUMNS: 18,
                                    plugin.CTR_ACT_CURRENT_COLUMNS: 18,
                                    plugin.CTR_ACT_UPDATE_COLUMNS: 18,
                                    plugin.CTR_ACT_DELTA_COLUMNS: 18,
                                },
                            },
                            "counter_at_least": {
                                plugin.CTR_SRC_DATA: {
                                    plugin.CTR_ACT_DELTA_ROWS: 14,
                                },
                            },
                        }),
                        custom_asserts=[
                            assert_custom_rows_delta(at_least=14)
                        ],
                        file_asserts={
                            "__balances_current*.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="1983-12-12", contiguous="days"),
                                assert_file_nones_per_row(),
                                assert_file_zeroes_per_col(exclude=r"Delta"),
                                assert_file_equal(),
                            ],
                            "_sheet_rates_balances*.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="1983-12-12", contiguous="days", descending=True),
                                assert_file_nones_per_row(),
                                assert_file_zeroes_per_row(),
                                assert_file_equal(),
                            ],
                            "_database_balances*.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="1983-12-12", contiguous="days"),
                                assert_file_nones_per_row(),
                                assert_file_zeroes_per_col(exclude=r"type=delta"),
                                assert_file_equal(),
                            ],
                        })

    ########################################################################################################################
    # Currency
    ########################################################################################################################

    # No current data, no new data, no remote source data downloads, no remote data repo downloads or uploads
    def test_currency_local_blank_1(self):
        fixture = _load_fixture("local", "currency", "blank_1")
        self.run_plugin("currency", plugin.RepoScope.LOCAL, "blank_1", log_level="info",
                        disable_sheet_downloads=True, disable_database_downloads=True, disable_drive_downloads=True, disable_source_downloads=True,
                        disable_sheet_uploads=True, disable_database_uploads=True, disable_drive_uploads=True,
                        enable_rerun=False, force_reprocessing=False, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_ERRORED: fixture["expected_errors"],
                                },
                            },
                        }),
                        file_asserts={
                            "__currency_current.csv": [
                                assert_file_does_not_exist(),
                            ],
                        })

    # No current data, corrupt data, no remote source data downloads, no remote data repo downloads or uploads
    def test_currency_local_corrupt_1(self):
        fixture = _load_fixture("local", "currency", "corrupt_1")
        self.run_plugin("currency", plugin.RepoScope.LOCAL, "corrupt_1", log_level="fatal",
                        disable_sheet_downloads=True, disable_database_downloads=True, disable_drive_downloads=True, disable_source_downloads=True,
                        disable_sheet_uploads=True, disable_database_uploads=True, disable_drive_uploads=True,
                        enable_rerun=False, force_reprocessing=True, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_ERRORED: fixture["expected_errors"],
                                },
                            },
                        }),
                        file_asserts={
                            "__currency_current.csv": [
                                assert_file_does_not_exist(),
                            ],
                        })

    # No current data, corrupt data, no remote source data downloads, no remote data repo downloads or uploads
    def test_currency_local_corrupt_2(self):
        fixture = _load_fixture("local", "currency", "corrupt_2")
        self.run_plugin("currency", plugin.RepoScope.LOCAL, "corrupt_2", log_level="fatal",
                        disable_sheet_downloads=True, disable_database_downloads=True, disable_drive_downloads=True, disable_source_downloads=True,
                        disable_sheet_uploads=True, disable_database_uploads=True, disable_drive_uploads=True,
                        enable_rerun=False, force_reprocessing=True, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_ERRORED: fixture["expected_errors"],
                                },
                            },
                        }),
                        file_asserts={
                            "__currency_current.csv": [
                                assert_file_does_not_exist(),
                            ],
                        })

    # Lots of current data, a specific amount of new data, no remote source data downloads, downloads and uploads from and to preview data repo
    def test_currency_preview_replete_1(self):
        fixture = _load_fixture("preview", "currency", "replete_1")
        drive_delete(REPOS_CURRENCY._scopes["preview"]["drive_folder"], "rba_fx_1987-1990.xls")
        drive_delete(REPOS_CURRENCY._scopes["preview"]["drive_folder"], "rba_fx_2023-current.xls")
        self.run_plugin("currency", plugin.RepoScope.PREVIEW, "replete_1", log_level="info",
                        disable_sheet_downloads=True, disable_database_downloads=True, disable_drive_downloads=False, disable_source_downloads=True,
                        disable_sheet_uploads=False, disable_database_uploads=True, disable_drive_uploads=False,
                        enable_rerun=True, force_reprocessing=False, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
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
                        }),
                        custom_asserts=[
                            assert_custom_rows_delta(equals=int(fixture["rows_delta"]))
                        ],
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
                        })

    # Lots of current data, a lot of live new data, downloads from remote sources, downloads from release data repo, no remote data repo uploads
    def test_currency_release_replete_1(self):
        fixture = _load_fixture("release", "currency", "replete_1")
        self.run_plugin("currency", plugin.RepoScope.RELEASE, "replete_1", log_level="info",
                        disable_sheet_downloads=False, disable_database_downloads=False, disable_drive_downloads=False, disable_source_downloads=False,
                        disable_sheet_uploads=True, disable_database_uploads=True, disable_drive_uploads=True,
                        enable_rerun=True, force_reprocessing=False, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
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
                        }),
                        custom_asserts=[
                            assert_custom_rows_delta(at_least=fixture["rows_delta"])
                        ],
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
                                assert_file_dates(start_date="1983-12-12", end_date_at_least=fixture["end_date"], contiguous="days"),
                                assert_file_nones_per_row(),
                                assert_file_equal(),
                            ],
                        })

    # Create a clean data cache for repopulating tests
    def test_currency_release_replete_1_download(self):
        self.run_plugin("currency", plugin.RepoScope.RELEASE, "replete_1", log_level="debug",
                        disable_sheet_downloads=True, disable_database_downloads=True, disable_drive_downloads=False, disable_source_downloads=False,
                        disable_sheet_uploads=True, disable_database_uploads=True, disable_drive_uploads=True,
                        enable_rerun=False, force_reprocessing=True, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_at_least": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_PROCESSED: 1,
                                },
                            },
                        }),
                        )

    ########################################################################################################################
    # Equity
    ########################################################################################################################

    # No current data, no new data, no remote source data downloads, no remote data repo downloads or uploads
    def test_equity_local_blank_1(self):
        fixture = _load_fixture("local", "equity", "blank_1")
        self.run_plugin("equity", plugin.RepoScope.LOCAL, "blank_1", log_level="info",
                        disable_sheet_downloads=True, disable_database_downloads=True, disable_drive_downloads=True, disable_source_downloads=True,
                        disable_sheet_uploads=True, disable_database_uploads=True, disable_drive_uploads=True,
                        enable_rerun=False, force_reprocessing=False, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_ERRORED: fixture["expected_errors"],
                                },
                            },
                        }),
                        file_asserts={
                            "__equity_current.csv": [
                                assert_file_does_not_exist(),
                            ],
                        })

    # No current data, corrupt data, no remote source data downloads, no remote data repo downloads or uploads
    def test_equity_local_corrupt_1(self):
        fixture = _load_fixture("local", "equity", "corrupt_1")
        self.run_plugin("equity", plugin.RepoScope.LOCAL, "corrupt_1", log_level="fatal",
                        disable_sheet_downloads=True, disable_database_downloads=True, disable_drive_downloads=True, disable_source_downloads=True,
                        disable_sheet_uploads=True, disable_database_uploads=True, disable_drive_uploads=True,
                        enable_rerun=False, force_reprocessing=True, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_ERRORED: fixture["expected_errors"],
                                },
                            },
                        }),
                        file_asserts={
                            "__equity_current.csv": [
                                assert_file_does_not_exist(),
                            ],
                        })

    # No current data, corrupt data, no remote source data downloads, no remote data repo downloads or uploads
    def test_equity_local_corrupt_2(self):
        fixture = _load_fixture("local", "equity", "corrupt_2")
        self.run_plugin("equity", plugin.RepoScope.LOCAL, "corrupt_2", log_level="debug",
                        disable_sheet_downloads=True, disable_database_downloads=True, disable_drive_downloads=True, disable_source_downloads=True,
                        disable_sheet_uploads=True, disable_database_uploads=True, disable_drive_uploads=True,
                        enable_rerun=False, force_reprocessing=True, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_ERRORED: fixture["expected_errors"],
                                },
                            },
                        }),
                        file_asserts={
                            "__equity_current.csv": [
                                assert_file_does_not_exist(),
                            ],
                        })

    # Lots of current data, a specific amount of new data, no remote source data downloads, no remote data repo downloads or uploads
    def test_equity_local_partial_1(self):
        fixture = _load_fixture("local", "equity", "partial_1")
        self.run_plugin("equity", plugin.RepoScope.LOCAL, "partial_1", log_level="info",
                        disable_sheet_downloads=True, disable_database_downloads=True, disable_drive_downloads=True, disable_source_downloads=True,
                        disable_sheet_uploads=True, disable_database_uploads=True, disable_drive_uploads=True,
                        enable_rerun=False, force_reprocessing=True, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_PROCESSED: int(fixture["files_processed"]),
                                },
                            },
                        }),
                        )

    # Lots of current data, a specific amount of new data, no remote source data downloads, no remote data repo downloads or uploads
    def test_equity_local_partial_2(self):
        fixture = _load_fixture("local", "equity", "partial_2")
        self.run_plugin("equity", plugin.RepoScope.LOCAL, "partial_2", log_level="info",
                        disable_sheet_downloads=True, disable_database_downloads=True, disable_drive_downloads=True, disable_source_downloads=True,
                        disable_sheet_uploads=True, disable_database_uploads=True, disable_drive_uploads=True,
                        enable_rerun=False, force_reprocessing=True, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_PROCESSED: int(fixture["files_processed"]),
                                },
                                plugin.CTR_SRC_DATA: {
                                    plugin.CTR_ACT_PREVIOUS_COLUMNS: fixture["cols_data"],
                                    plugin.CTR_ACT_CURRENT_COLUMNS: fixture["cols_data"],
                                    plugin.CTR_ACT_UPDATE_COLUMNS: fixture["cols_data"],
                                    plugin.CTR_ACT_DELTA_COLUMNS: fixture["cols_data"],
                                    plugin.CTR_ACT_DELTA_ROWS: int(fixture["rows_delta"]),
                                },
                            },
                        }),
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
                        })

    # Lots of current data, a specific amount of new data, no remote source data downloads, no remote data repo downloads or uploads
    def test_equity_local_replete_1(self):
        fixture = _load_fixture("local", "equity", "replete_1")
        self.run_plugin("equity", plugin.RepoScope.LOCAL, "replete_1", log_level="info",
                        disable_sheet_downloads=True, disable_database_downloads=True, disable_drive_downloads=True, disable_source_downloads=True,
                        disable_sheet_uploads=True, disable_database_uploads=True, disable_drive_uploads=True,
                        enable_rerun=False, force_reprocessing=True, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_PROCESSED: int(fixture["files_processed"]),
                                },
                                plugin.CTR_SRC_DATA: {
                                    plugin.CTR_ACT_PREVIOUS_COLUMNS: fixture["cols_data"],
                                    plugin.CTR_ACT_CURRENT_COLUMNS: fixture["cols_data"],
                                    plugin.CTR_ACT_UPDATE_COLUMNS: fixture["cols_data"],
                                    plugin.CTR_ACT_DELTA_COLUMNS: fixture["cols_data"],
                                    plugin.CTR_ACT_DELTA_ROWS: int(fixture["rows_delta"]),
                                },
                            },
                        }),
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
                        })

    # Lots of current data, a specific amount of new data, no remote source data downloads, downloads and uploads from and to preview data repo
    def test_equity_preview_replete_1(self):
        fixture = _load_fixture("preview", "equity", "replete_1")
        drive_delete(REPOS_EQUITY._scopes["preview"]["drive_folder"], "yahoo_acdc_2018.csv")
        self.run_plugin("equity", plugin.RepoScope.PREVIEW, "replete_1", log_level="info",
                        disable_sheet_downloads=True, disable_database_downloads=True, disable_drive_downloads=False, disable_source_downloads=True,
                        disable_sheet_uploads=False, disable_database_uploads=True, disable_drive_uploads=False,
                        enable_rerun=True, force_reprocessing=False, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
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
                        }),
                        custom_asserts=[
                            assert_custom_rows_delta(equals=int(fixture["rows_delta"]))
                        ],
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
                        })

    # Lots of current data, a lot of live new data, downloads from remote sources, downloads from release data repo, no remote data repo uploads
    def test_equity_release_replete_1(self):
        fixture = _load_fixture("release", "equity", "replete_1")
        self.run_plugin("equity", plugin.RepoScope.RELEASE, "replete_1", log_level="info",
                        disable_sheet_downloads=False, disable_database_downloads=False, disable_drive_downloads=False, disable_source_downloads=False,
                        disable_sheet_uploads=True, disable_database_uploads=True, disable_drive_uploads=True,
                        enable_rerun=True, force_reprocessing=False, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
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
                        }),
                        custom_asserts=[
                            assert_custom_rows_delta(at_least=fixture["rows_delta"])
                        ],
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
                                assert_file_dates(start_date="1982-04-01", end_date_at_least=fixture["end_date"], contiguous="days"),
                                assert_file_nones_per_col(after_first_rows=True),
                                assert_file_equal(),
                            ],
                        })

    # Create a clean data cache for repopulating tests
    def test_equity_release_replete_1_download(self):
        self.run_plugin("equity", plugin.RepoScope.RELEASE, "replete_1", log_level="debug",
                        disable_sheet_downloads=False, disable_database_downloads=False, disable_drive_downloads=False, disable_source_downloads=False,
                        disable_sheet_uploads=True, disable_database_uploads=True, disable_drive_uploads=True,
                        enable_rerun=False, force_reprocessing=True, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_at_least": {
                                plugin.CTR_SRC_SOURCES: {
                                    plugin.CTR_ACT_DOWNLOADED: 1,
                                },
                            },
                        }),
                        )

    ########################################################################################################################
    # Interest
    ########################################################################################################################

    # No current data, no new data, no remote source data downloads, no remote data repo downloads or uploads
    def test_interest_local_blank_1(self):
        fixture = _load_fixture("local", "interest", "blank_1")
        self.run_plugin("interest", plugin.RepoScope.LOCAL, "blank_1", log_level="info",
                        disable_sheet_downloads=True, disable_database_downloads=True, disable_drive_downloads=True, disable_source_downloads=True,
                        disable_sheet_uploads=True, disable_database_uploads=True, disable_drive_uploads=True,
                        enable_rerun=False, force_reprocessing=False, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_ERRORED: fixture["expected_errors"],
                                },
                            },
                        }),
                        file_asserts={
                            "__interest_current.csv": [
                                assert_file_does_not_exist(),
                            ],
                        })

    # No current data, corrupt data, no remote source data downloads, no remote data repo downloads or uploads
    def test_interest_local_corrupt_1(self):
        fixture = _load_fixture("local", "interest", "corrupt_1")
        self.run_plugin("interest", plugin.RepoScope.LOCAL, "corrupt_1", log_level="fatal",
                        disable_sheet_downloads=True, disable_database_downloads=True, disable_drive_downloads=True, disable_source_downloads=True,
                        disable_sheet_uploads=True, disable_database_uploads=True, disable_drive_uploads=True,
                        enable_rerun=False, force_reprocessing=True, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_ERRORED: fixture["expected_errors"],
                                },
                            },
                        }),
                        file_asserts={
                            "__interest_current.csv": [
                                assert_file_does_not_exist(),
                            ],
                        })

    # No current data, corrupt data, no remote source data downloads, no remote data repo downloads or uploads
    def test_interest_local_corrupt_2(self):
        fixture = _load_fixture("local", "interest", "corrupt_2")
        self.run_plugin("interest", plugin.RepoScope.LOCAL, "corrupt_2", log_level="fatal",
                        disable_sheet_downloads=True, disable_database_downloads=True, disable_drive_downloads=True, disable_source_downloads=True,
                        disable_sheet_uploads=True, disable_database_uploads=True, disable_drive_uploads=True,
                        enable_rerun=False, force_reprocessing=True, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_ERRORED: fixture["expected_errors"],
                                },
                            },
                        }),
                        file_asserts={
                            "__interest_current.csv": [
                                assert_file_does_not_exist(),
                            ],
                        })

    # Lots of current data, a specific amount of new data, no remote source data downloads, downloads and uploads from and to preview data repo
    def test_interest_preview_replete_1(self):
        fixture = _load_fixture("preview", "interest", "replete_1")
        drive_delete(REPOS_INTEREST._scopes["preview"]["drive_folder"], "inflation.xlsx")
        self.run_plugin("interest", plugin.RepoScope.PREVIEW, "replete_1", log_level="info",
                        disable_sheet_downloads=True, disable_database_downloads=True, disable_drive_downloads=False, disable_source_downloads=True,
                        disable_sheet_uploads=False, disable_database_uploads=True, disable_drive_uploads=False,
                        enable_rerun=True, force_reprocessing=False, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
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
                        }),
                        custom_asserts=[
                            assert_custom_rows_delta(equals=int(fixture["rows_delta"]))
                        ],
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
                        })

    # Lots of current data, a lot of live new data, downloads from remote sources, downloads from release data repo, no remote data repo uploads
    def test_interest_release_replete_1(self):
        fixture = _load_fixture("release", "interest", "replete_1")
        self.run_plugin("interest", plugin.RepoScope.RELEASE, "replete_1", log_level="info",
                        disable_sheet_downloads=False, disable_database_downloads=False, disable_drive_downloads=False, disable_source_downloads=False,
                        disable_sheet_uploads=True, disable_database_uploads=True, disable_drive_uploads=True,
                        enable_rerun=True, force_reprocessing=False, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
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
                        }),
                        custom_asserts=[
                            assert_custom_rows_delta(at_least=fixture["rows_delta"])
                        ],
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
                                assert_file_dates(start_date="1982-04-01", end_date_at_least=fixture["end_date"], contiguous="months"),
                                assert_file_nones_per_row(exclude=r"type=mean"),
                                assert_file_equal(),
                            ],
                        })

    # Create a clean data cache for repopulating tests
    def test_interest_release_replete_1_download(self):
        self.run_plugin("interest", plugin.RepoScope.RELEASE, "replete_1", log_level="debug",
                        disable_sheet_downloads=True, disable_database_downloads=True, disable_drive_downloads=False, disable_source_downloads=False,
                        disable_sheet_uploads=True, disable_database_uploads=True, disable_drive_uploads=True,
                        enable_rerun=False, force_reprocessing=True, force_downloads=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_at_least": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_PROCESSED: 1,
                                },
                            },
                        }),
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
            return {"ts": run_ts.isoformat(), "bucket": int(run_ts.timestamp()) // (30 * 60), "plugins": run_plugins, "errored": errored}

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
                    buckets[plugin_key][source_key][action_key] = {"sum": tmp_value * count, "min": max(0, tmp_value - 3), "max": tmp_value + 3, "count": count}
            return {"date": date.isoformat(), "errored_runs": errored_runs, "buckets": buckets}

        plugins = ["balances", "currency", "equity", "interest"]
        all_plugin_names = ["summary"] + sorted(plugins)
        output_dir = abspath(join(DIR_ROOT, "target", "runtime-dashboard"))
        os.makedirs(output_dir, exist_ok=True)
        static_copy = join(output_dir, "static")
        if os.path.islink(static_copy) or os.path.isfile(static_copy):
            os.unlink(static_copy)
        elif os.path.isdir(static_copy):
            shutil.rmtree(static_copy)
        os.makedirs(static_copy, exist_ok=True)
        for file_name in os.listdir(WEB_ROOT_DIR):
            if os.path.splitext(str(file_name))[1] in {".css", ".js", ".mp3"}:
                shutil.copy2(join(WEB_ROOT_DIR, str(file_name)), join(static_copy, str(file_name)))
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
            plugin_sections = [{"id": "summary", "title": "Summary", "theme": "ghost-gray"}] + [
                {"id": plugin_name, "title": plugin_name.capitalize(), "theme": THEMES[index % len(THEMES)]}
                for index, plugin_name in enumerate(p for p in snapshot.plugins if p != "summary")
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
            latest_run_json = json.dumps({"ts": adhoc_ts.isoformat(), "plugins": adhoc_plugins, "errored": adhoc_errored})
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
            history = RunHistory(plugins=["balances"], cache_dir=tmp, poll_period_minutes=30, raw_label="1d")
            history.add_run(datetime.datetime.now(tz=CTR_TZ), {"balances": counters})

            filtered_history = RunHistory(plugins=["currency"], cache_dir=tmp, poll_period_minutes=30, raw_label="1d")
            filtered_history.load()

            self.assertEqual(0, len(filtered_history._raw))
            self.assertEqual(0, len(filtered_history._day))

    def test_dashboard_history_malformed_entries_start_fresh(self):
        counters = {
            plugin.CTR_SRC_FILES: {
                plugin.CTR_ACT_PROCESSED: 1,
                plugin.CTR_ACT_ERRORED: 0,
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            history = RunHistory(plugins=["balances"], cache_dir=tmp, poll_period_minutes=30, raw_label="1d")
            history.add_run(datetime.datetime.now(tz=CTR_TZ), {"balances": counters})

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

            loaded = RunHistory(plugins=["balances"], cache_dir=tmp, poll_period_minutes=30, raw_label="1d")
            loaded.load()

            self.assertEqual(0, len(loaded._raw))
            self.assertEqual(0, len(loaded._day))

    ########################################################################################################################
    # Sources
    ########################################################################################################################

    def test_library_sheet(self):
        test = PluginStub("Test", "SOME_NON_EXISTANT_GUID")

        def _sheet_read(_result, schema=None):
            if schema is None:
                schema = {}
            if _result.status == DownloadStatus.FAILED:
                return test.dataframe_new()
            return test.csv_read(_result.file_path, schema=schema)

        plugin.config.log_level = "fatal"
        missing = test.sheet_download("!", "missing", sheet_load_secs=0, sheet_retry_max=1)
        self.assertEqual(DownloadStatus.FAILED, missing.status)
        self.assertEqual(0, len(_sheet_read(missing)))
        loading = test.sheet_download("1bUpZCIOM-olcxLQ7_fdgi4Nu7GOQC30sK_LALZ2B0bs", "loading", sheet_load_secs=0, sheet_retry_max=1)
        self.assertEqual(DownloadStatus.FAILED, loading.status)
        self.assertEqual(0, len(_sheet_read(loading)))

        plugin.config.log_level = "info"
        empty = test.sheet_download("1nPtCOciS81Y-FWJZ8pi5-9Fd6RZ6_EqyfweBekFH6s4", "empty")
        self.assertEqual(DownloadStatus.DOWNLOADED, empty.status)
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
        self.assertEqual(DownloadStatus.DOWNLOADED, typed.status)
        typed_number = _sheet_read(typed, schema=test_type_number)
        self.assertEqual(test_str.format(*[test.dataframe_type_to_str(dtype) for dtype in test_type_number.values()]), test.dataframe_to_str(typed_number))
        self.assertEqual(4, len(typed_number))
        typed_utf = _sheet_read(typed, schema=test_type_utf)
        self.assertEqual(test_str.format(*["String" for _ in test_type_utf]), test.dataframe_to_str(typed_utf))
        self.assertEqual(4, len(typed_utf))

        data_key = "1Kf9-Gk7aD4aBdq2JCfz5zVUMWAtvJo2ZfqmSQyo8Bjk"
        data_str = "[Exchange Symbol(String), Port Quantity({}), Unit Price(Float64), Watch Value(Float64), Watch Quantity(Int64), Base Quantity(Int64)]"
        download = test.sheet_download(data_key, "Index_weights", "Indexes", 2, check=True)
        self.assertEqual(DownloadStatus.DOWNLOADED, download.status)
        validated = test.sheet_download(data_key, "Index_weights", "Indexes", 2, check=True)
        self.assertEqual(DownloadResult(DownloadStatus.CACHED, download.file_path), validated)
        blind = test.sheet_download(data_key, "Index_weights", "Indexes", 2, check=False)
        self.assertEqual(DownloadResult(DownloadStatus.CACHED, download.file_path), blind)
        plugin.config.force_downloads = True
        forced = test.sheet_download(data_key, "Index_weights", "Indexes", 2, check=False)
        self.assertEqual(DownloadResult(DownloadStatus.DOWNLOADED, download.file_path), forced)
        plugin.config.force_downloads = False
        data_df = _sheet_read(download)
        self.assertEqual(data_str.format("Float64"), test.dataframe_to_str(data_df))
        self.assertEqual(24, len(data_df))
        data_df = _sheet_read(download, schema={"Port Quantity": pl.Utf8})
        self.assertEqual(data_str.format(test.dataframe_type_to_str(pl.Utf8)), test.dataframe_to_str(data_df))
        self.assertEqual(24, len(data_df))

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
            self.assertEqual(DownloadResult(DownloadStatus.FAILED, None), result)
        self.assertFalse(isfile(invalid_path))

        cache_cache = "Cache"
        cache_path = abspath(f"{test.local_cache}/_database_{cache_cache.lower()}.csv")
        with open(cache_path, "w") as fh:
            fh.write("time,entity,type,period,unit,value\n2020-01-01,AUD/USD,snapshot,1d,$,0.65\n")
        self.assertEqual(DownloadResult(DownloadStatus.CACHED, cache_path), test.database_download(cache_cache, "SELECT 1"))
        plugin.config.disable_source_downloads = True
        self.assertEqual(DownloadResult(DownloadStatus.CACHED, cache_path), test.database_download(cache_cache, "SELECT 1"))
        reset_config()

        test.reset_counters()
        test.database_upload(test.dataframe_new())
        test.database_upload(pl.DataFrame({"Date": pl.Series([], dtype=pl.Date)}))
        self.assertFalse(csv_path in test._db_cache_dfs)
        self.assertEqual(0, test.get_counter(plugin.CTR_SRC_EGRESS, plugin.CTR_ACT_DATABASE_ROWS))
        self.assertEqual(0, test.get_counter(plugin.CTR_SRC_EGRESS, plugin.CTR_ACT_DATABASE_COLUMNS))

        test.reset_counters()
        equity_df = pl.DataFrame({
            "Date": pl.Series([date_type(2024, 1, 1), date_type(2024, 1, 2), date_type(2024, 1, 3)], dtype=pl.Date),
            "AORD Price Close": [729.0, 726.5, 721.4],
        })
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
        currency_df = pl.DataFrame({
            "Date": pl.Series([date_type(2024, 1, 1), date_type(2024, 1, 2)], dtype=pl.Date),
            "AUD/USD": [0.65, 0.66],
            "AUD/GBP": [0.50, 0.51],
            "AUD/SGD": [0.90, 0.91],
        })
        test.database_upload(currency_df, metric_type="snapshot", period="1d", unit="$")
        long_df = test._db_cache_dfs[csv_path]
        self.assertEqual(6, len(long_df))
        self.assertEqual({"AUD/USD", "AUD/GBP", "AUD/SGD"}, set(long_df["entity"].to_list()))
        self.assertEqual({"snapshot"}, set(long_df["type"].to_list()))
        self.assertEqual(3, test.get_counter(plugin.CTR_SRC_EGRESS, plugin.CTR_ACT_DATABASE_COLUMNS))
        self.assertEqual(2, test.get_counter(plugin.CTR_SRC_EGRESS, plugin.CTR_ACT_DATABASE_ROWS))

        test.reset_counters()
        test._db_cache_dfs.clear()
        sparse_df = pl.DataFrame({
            "Date": pl.Series([date_type(2024, 2, 1), date_type(2024, 2, 2), date_type(2024, 2, 3)], dtype=pl.Date),
            "AXJO Price Close": [5000.0, None, 5100.0],
        })
        test.database_upload(sparse_df, metric_type="price-close", period="1d", unit="$")
        long_df = test._db_cache_dfs[csv_path]
        self.assertEqual(2, len(long_df))
        self.assertNotIn(None, long_df["value"].to_list())
        self.assertEqual(3, test.get_counter(plugin.CTR_SRC_EGRESS, plugin.CTR_ACT_DATABASE_ROWS))

        test.reset_counters()
        test._db_cache_dfs.clear()
        call1 = pl.DataFrame({
            "Date": pl.Series([date_type(2024, 3, 1), date_type(2024, 3, 2)], dtype=pl.Date),
            "AUD/USD": [0.65, 0.66],
        })
        call2 = pl.DataFrame({
            "Date": pl.Series([date_type(2024, 3, 2), date_type(2024, 3, 3)], dtype=pl.Date),
            "AUD/USD": [0.67, 0.68],
        })
        test.database_upload(call1, metric_type="snapshot", period="1d", unit="$")
        test.database_upload(call2, metric_type="snapshot", period="1d", unit="$")
        long_df = test._db_cache_dfs[csv_path]
        self.assertEqual(3, len(long_df))
        mar2 = long_df.filter(pl.col("time") == date_type(2024, 3, 2))
        self.assertEqual(1, len(mar2))
        self.assertEqual(0.67, mar2["value"][0])

        test.reset_counters()
        test._db_cache_dfs.clear()
        snapshot_df = pl.DataFrame({
            "Date": pl.Series([date_type(2024, 4, 1)], dtype=pl.Date),
            "AUD/USD": [0.65],
        })
        delta_df = pl.DataFrame({
            "Date": pl.Series([date_type(2024, 4, 1)], dtype=pl.Date),
            "AUD/USD": [-1.53],
        })
        test.database_upload(snapshot_df, metric_type="snapshot", period="1d", unit="$")
        test.database_upload(delta_df, metric_type="delta", period="1d", unit="%")
        long_df = test._db_cache_dfs[csv_path]
        self.assertEqual(2, len(long_df))
        self.assertEqual({"snapshot", "delta"}, set(long_df["type"].to_list()))
        self.assertEqual({"$", "%"}, set(long_df["unit"].to_list()))

    def test_dump_database_queries(self):
        reset_config()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            wrangle_main._dump_database_queries()
        text = output.getvalue()
        print(text)
        for plugin_name in wrangle_main._get_plugins():
            instance = wrangle_main._instantiate_plugin(plugin_name)
            if instance.database:
                self.assertIn(f"# {plugin_name}", text)
                self.assertEqual(text.count(f"FROM {plugin_name}"), len(database.DATABASE_QUERY_TEMPLATES))
            else:
                self.assertNotIn(f"# {plugin_name}\n", text)

    def test_library_dataframe(self):
        test = PluginStub("Test", "SOME_NON_EXISTANT_GUID")

        df_empty_str = "[{}]"
        df_empty_type = {"C1": pl.Int16}
        self.assertEqual(df_empty_str.format(""), test.dataframe_to_str(test.dataframe_new()))
        self.assertEqual(df_empty_str.format(""), test.dataframe_to_str(test.dataframe_new([])))
        self.assertEqual(df_empty_str.format(""), test.dataframe_to_str(test.dataframe_new([], {})))
        self.assertEqual(df_empty_str.format("C1(Int16)"), test.dataframe_to_str(test.dataframe_new([], df_empty_type)))

        df_data_str = "[C1({}), C2({}), C3({})]"
        df_data_type = {"C1": pl.Int64, "C2": pl.Utf8, "C3": pl.Utf8}
        df_data = [{"C1": 1, "C2": 1.1, "C3": "1"}, {"C1": 2, "C2": 2.2, "C3": "2"}, {"C1": None, "C2": None, "C3": None}]
        self.assertEqual(df_data_str.format("Int64", "Float64", "String"), test.dataframe_to_str(test.dataframe_new(df_data)))
        self.assertEqual(df_data_str.format("Int64", "Float64", "String"), test.dataframe_to_str(test.dataframe_new(df_data, {})))
        self.assertEqual(df_data_str.format("Int64", "String", "String"), test.dataframe_to_str(test.dataframe_new(df_data, df_data_type)))
        self.assertEqual(3, len(test.dataframe_new(df_data, schema={column: pl.Utf8 for column in df_data[0]})))

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
        self.assertEqual(df_lots_rows, len(test.dataframe_new(df_lots, schema={column: pl.Utf8 for column in df_data[0]})))
        self.assertEqual(df_lots_rows, len(test.dataframe_new(df_lots, schema={column: pl.Utf8 for column in df_lots[0]})))

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
        delta, current, previous = t.state_cache(update)
        self.assertEqual(1, len(delta))
        self.assertEqual(2.5, delta["Value"][0])

    def test_state_cache_new_column(self):
        t = self._setup_state_test("test-4")
        update = pl.DataFrame({
            "Date": ["2020-01-01", "2020-02-01"],
            "Value": [1.0, 2.0],
            "Extra": [10.0, 20.0],
        }).with_columns(pl.col("Date").str.to_date())
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
        delta, current, _ = t.state_cache(
            update,
            lambda df: df.with_columns((pl.col("Value") * 2).alias("Double"))
        )
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
        update = pl.DataFrame({
            "Date": ["2020-01-01", "2020-01-01", "2020-02-01"],
            "Value": [1.0, 9.9, 2.0],
        }).with_columns(pl.col("Date").str.to_date())
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
        self.assertEqual(
            ["2020-01-01", "2020-02-01", "2020-03-01", "2020-04-01"],
            [str(d) for d in current.sort("Date")["Date"].to_list()]
        )

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
        update = pl.DataFrame({
            "Date": ["2020-01-01", "2020-02-01"],
            "Value": [9.0, 9.0],
            "Extra": [90.0, 90.0],
        }).with_columns(pl.col("Date").str.to_date())
        delta, current, _ = t.state_cache(update)
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
        run2 = pl.DataFrame({
            "Date": ["2020-01-01", "2020-02-01"],
            "Value": [1.0, 2.0],
            "Extra": [10.0, 20.0],
        }).with_columns(pl.col("Date").str.to_date())
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
        update = pl.DataFrame({
            "Date": [None, "2020-01-01", "2020-02-01"],
            "Value": [99.0, 1.0, 2.0],
        }).with_columns(pl.col("Date").str.to_date(strict=False))
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
        update = pl.DataFrame({
            "Date": ["2020-01-01", "2020-02-01"],
            "Value": [1.0, 2.0],
            "Extra": [10.0, 20.0],
            "Third": [100.0, 200.0],
        }).with_columns(pl.col("Date").str.to_date())
        t.state_cache(update)
        self.assertEqual(3, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_PREVIOUS_COLUMNS))

    def _price_df(self, date_price_pairs, ticker="AAPL"):
        return pl.DataFrame({
            "Date": [p[0] for p in date_price_pairs],
            f"{ticker} Price Close": [float(p[1]) for p in date_price_pairs],
        }).with_columns(pl.col("Date").str.to_date())

    def _price_change_agg(self, ticker="AAPL"):
        price_col = f"{ticker} Price Close"
        change_col = f"{ticker} Price Close 1d-Change Percentage"

        def _agg(df):
            str_cols = [c for c, t in zip(df.columns, df.dtypes, strict=False) if _is_string_col(c, t)]
            if str_cols:
                df = df.with_columns([pl.col(c).cast(pl.Float64, strict=False) for c in str_cols])
            if price_col in df.columns:
                df = df.with_columns(
                    pl.when(pl.col(price_col).is_null()).then(None)
                    .otherwise(pl.col(price_col).pct_change(1).fill_nan(None) * 100)
                    .alias(change_col)
                )
                df = df.with_columns(
                    pl.when(pl.col(price_col).is_not_null() & pl.col(change_col).is_null())
                    .then(pl.lit(0.0)).otherwise(pl.col(change_col)).alias(change_col)
                )
            out_cols = [c for c in ["Date", price_col, change_col] if c in df.columns]
            out = df.select(out_cols)
            return out.with_columns(pl.col(change_col).round(4)) if change_col in out.columns else out

        return _agg

    def test_state_cache_aggregate_derived_columns(self):
        t = self._setup_state_test("agg-1")
        data = self._price_df([
            ("2020-01-01", 100.0), ("2020-02-01", 200.0), ("2020-03-01", 300.0),
        ])
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
        data = self._price_df([
            ("2020-01-01", 100.0), ("2020-02-01", 200.0), ("2020-03-01", 300.0),
        ])
        t.state_cache(data, self._price_change_agg())
        t.reset_counters()
        delta, current, _ = t.state_cache(data, self._price_change_agg())
        self.assertEqual(0, len(delta))
        self.assertEqual(3, len(current))
        self.assertEqual(0, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_DELTA_ROWS))
        self.assertEqual(3, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_CURRENT_ROWS))

    def test_state_cache_aggregate_cross_boundary(self):
        t = self._setup_state_test("agg-3")
        t.state_cache(self._price_df([
            ("2020-01-01", 100.0), ("2020-02-01", 200.0), ("2020-03-01", 300.0),
        ]), self._price_change_agg())
        t.reset_counters()
        delta, current, _ = t.state_cache(self._price_df([
            ("2020-01-01", 100.0), ("2020-02-01", 200.0), ("2020-03-01", 300.0),
            ("2020-04-01", 400.0), ("2020-05-01", 600.0),
        ]), self._price_change_agg())
        self.assertEqual(2, len(delta))
        self.assertEqual(5, len(current))
        delta_sorted = delta.sort("Date")
        self.assertEqual(33.3333, delta_sorted["AAPL Price Close 1d-Change Percentage"][0])
        self.assertEqual(50.0, delta_sorted["AAPL Price Close 1d-Change Percentage"][1])

    def test_state_cache_aggregate_narrows_columns(self):
        t = self._setup_state_test("agg-4")
        data = pl.DataFrame({
            "Date": ["2020-01-01", "2020-02-01"],
            "AAPL Price Close": [100.0, 200.0],
            "AAPL Market Volume": [1000.0, 2000.0],
            "AAPL Currency Base": ["AUD", "AUD"],
        }).with_columns(pl.col("Date").str.to_date())
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

        data = pl.DataFrame({
            "Date": ["2020-01-01", "2020-02-01"],
            "AAPL Price Close": [100.0, 200.0],
        }).with_columns(pl.col("Date").str.to_date())

        _, current1, _ = t.state_cache(data, agg_with_null_col)
        self.assertEqual(pl.Float64, current1["AAPL Baseline Price Close"].dtype)
        t.reset_counters()
        delta2, current2, _ = t.state_cache(data, agg_with_null_col)
        self.assertEqual(0, len(delta2))
        self.assertEqual(pl.Float64, current2["AAPL Baseline Price Close"].dtype)

    def test_state_cache_csv_files_written(self):
        t = self._setup_state_test("agg-6")
        t.state_cache(self._price_df([
            ("2020-01-01", 100.0), ("2020-02-01", 200.0),
        ]), self._price_change_agg())
        self.assertTrue(isfile(join(t.local_cache, "__test_current.csv")))
        self.assertTrue(isfile(join(t.local_cache, "__test_update.csv")))
        self.assertTrue(isfile(join(t.local_cache, "__test_delta.csv")))
        self.assertFalse(isfile(join(t.local_cache, "__test_previous.csv")))
        t.reset_counters()
        t.state_cache(self._price_df([
            ("2020-01-01", 100.0), ("2020-02-01", 200.0),
            ("2020-03-01", 300.0), ("2020-04-01", 400.0),
        ]), self._price_change_agg())
        self.assertTrue(isfile(join(t.local_cache, "__test_previous.csv")))
        self.assertEqual(4, len(t.csv_read(join(t.local_cache, "__test_current.csv"))))
        self.assertEqual(2, len(t.csv_read(join(t.local_cache, "__test_previous.csv"))))
        self.assertEqual(4, len(t.csv_read(join(t.local_cache, "__test_update.csv"))))
        self.assertEqual(2, len(t.csv_read(join(t.local_cache, "__test_delta.csv"))))

    def test_state_cache_row_and_column_counters(self):
        t = self._setup_state_test("agg-7")
        t.state_cache(self._price_df([
            ("2020-01-01", 100.0), ("2020-02-01", 200.0), ("2020-03-01", 300.0),
        ]), self._price_change_agg())
        self.assertEqual(3, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_CURRENT_ROWS))
        self.assertEqual(3, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_UPDATE_ROWS))
        self.assertEqual(3, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_DELTA_ROWS))
        self.assertEqual(0, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_PREVIOUS_ROWS))
        self.assertEqual(2, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_CURRENT_COLUMNS))
        t.reset_counters()
        t.state_cache(self._price_df([
            ("2020-01-01", 100.0), ("2020-02-01", 200.0), ("2020-03-01", 300.0),
            ("2020-04-01", 400.0),
        ]), self._price_change_agg())
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
                df = df.with_columns(
                    pl.when(pl.col("AAPL Derived").is_null())
                    .then(pl.col("AAPL Price Close") * 10.0)
                    .otherwise(pl.col("AAPL Derived"))
                    .alias("AAPL Derived"))
            out_cols = [c for c in ["Date", "AAPL Price Close", "AAPL Derived"] if c in df.columns]
            return df.select(out_cols)

        t = self._setup_state_test("agg-8")
        _, current1, _ = t.state_cache(
            self._price_df([("2020-01-01", 1.0), ("2020-02-01", 2.0)]), null_fill_agg)
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
                df = df.with_columns(
                    pl.when(pl.col("AAPL Derived").is_null())
                    .then(pl.col("AAPL Price Close") * 10.0)
                    .otherwise(pl.col("AAPL Derived"))
                    .alias("AAPL Derived"))
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
        return pl.DataFrame({
            "Date": [r[0] for r in rows],
            "Account ID": [r[1] for r in rows],
            "Balance": [float(r[2]) for r in rows],
        }).with_columns(pl.col("Date").str.to_date())

    def test_state_cache_multi_key_first_run(self):
        t = self._setup_state_test("mk-1")
        delta, current, previous = t.state_cache(
            self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]),
            key_columns=["Date", "Account ID"])
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
        t.state_cache(self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]),
                      key_columns=["Date", "Account ID"])
        t.reset_counters()
        delta, current, _ = t.state_cache(
            self._multi_key_dataframe([("2026-01-01", "acc-1", 150.0), ("2026-01-01", "acc-2", 200.0)]),
            key_columns=["Date", "Account ID"])
        self.assertEqual(1, len(delta))
        self.assertEqual(150.0, delta.filter(pl.col("Account ID") == "acc-1")["Balance"][0])
        self.assertEqual(2, len(current))

    def test_state_cache_multi_key_new_account(self):
        t = self._setup_state_test("mk-4")
        t.state_cache(self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0)]),
                      key_columns=["Date", "Account ID"])
        t.reset_counters()
        delta, current, _ = t.state_cache(
            self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]),
            key_columns=["Date", "Account ID"])
        self.assertEqual(1, len(delta))
        self.assertEqual("acc-2", delta["Account ID"][0])
        self.assertEqual(2, len(current))

    def test_state_cache_multi_key_new_date(self):
        t = self._setup_state_test("mk-5")
        t.state_cache(self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]),
                      key_columns=["Date", "Account ID"])
        t.reset_counters()
        delta, current, _ = t.state_cache(
            self._multi_key_dataframe([("2026-01-02", "acc-1", 110.0), ("2026-01-02", "acc-2", 210.0)]),
            key_columns=["Date", "Account ID"])
        self.assertEqual(2, len(delta))
        self.assertEqual(4, len(current))
        self.assertTrue(all(str(d) == "2026-01-02" for d in delta["Date"].to_list()))

    def test_state_cache_multi_key_partial_update(self):
        t = self._setup_state_test("mk-6")
        t.state_cache(self._multi_key_dataframe([
            ("2026-01-01", "acc-1", 100.0),
            ("2026-01-01", "acc-2", 200.0),
        ]), key_columns=["Date", "Account ID"])
        t.reset_counters()
        delta, current, _ = t.state_cache(self._multi_key_dataframe([
            ("2026-01-01", "acc-1", 150.0),
            ("2026-01-01", "acc-2", 200.0),
            ("2026-01-02", "acc-1", 155.0),
        ]), key_columns=["Date", "Account ID"])
        self.assertEqual(2, len(delta))
        delta_sorted = delta.sort(["Date", "Account ID"])
        self.assertEqual("2026-01-01", str(delta_sorted["Date"][0]))
        self.assertEqual("acc-1", delta_sorted["Account ID"][0])
        self.assertEqual("2026-01-02", str(delta_sorted["Date"][1]))

    def test_state_cache_multi_key_duplicate_keys_in_update(self):
        t = self._setup_state_test("mk-7")
        delta, current, _ = t.state_cache(self._multi_key_dataframe([
            ("2026-01-01", "acc-1", 100.0),
            ("2026-01-01", "acc-1", 999.0),
        ]), key_columns=["Date", "Account ID"])
        self.assertEqual(1, len(current))
        self.assertEqual(999.0, current["Balance"][0])
        self.assertEqual(1, len(delta))

    def test_state_cache_multi_key_update_supersedes_current(self):
        t = self._setup_state_test("mk-8")
        t.state_cache(self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0)]),
                      key_columns=["Date", "Account ID"])
        t.reset_counters()
        delta, current, previous = t.state_cache(
            self._multi_key_dataframe([("2026-01-01", "acc-1", 999.0)]),
            key_columns=["Date", "Account ID"])
        self.assertEqual(1, len(delta))
        self.assertEqual(999.0, current["Balance"][0])
        self.assertEqual(100.0, previous["Balance"][0])

    def test_state_cache_multi_key_counters(self):
        t = self._setup_state_test("mk-9")
        t.state_cache(self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0)]),
                      key_columns=["Date", "Account ID"])
        self.assertEqual(1, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_UPDATE_COLUMNS))
        self.assertEqual(1, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_CURRENT_COLUMNS))
        self.assertEqual(1, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_DELTA_COLUMNS))

    def test_state_cache_multi_key_clean(self):
        t = self._setup_state_test("mk-10")
        t.state_cache(self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]),
                      key_columns=["Date", "Account ID"])
        t.reset_counters()
        plugin.config.force_reprocessing = True
        delta, current, previous = t.state_cache(
            self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]),
            key_columns=["Date", "Account ID"])
        self.assertEqual(2, len(delta))
        self.assertEqual(2, len(current))
        self.assertEqual(0, len(previous))

    def test_state_cache_multi_key_with_aggregate(self):
        t = self._setup_state_test("mk-12")

        def _agg(df):
            if "Balance" in df.columns:
                df = df.with_columns((pl.col("Balance") * 2).alias("Balance Double"))
            return df

        delta, current, _ = t.state_cache(
            self._multi_key_dataframe([("2026-01-01", "acc-1", 50.0), ("2026-01-01", "acc-2", 100.0)]),
            aggregate_func=_agg, key_columns=["Date", "Account ID"])
        self.assertIn("Balance Double", current.columns)
        doubles = current.sort(["Date", "Account ID"])["Balance Double"].to_list()
        self.assertEqual([100.0, 200.0], doubles)

    def test_state_cache_multi_key_null_date_dropped(self):
        t = self._setup_state_test("mk-13")
        data = pl.DataFrame({
            "Date": [None, "2026-01-01"],
            "Account ID": ["acc-x", "acc-1"],
            "Balance": [999.0, 100.0],
        }).with_columns(pl.col("Date").str.to_date(strict=False))
        delta, current, _ = t.state_cache(data, key_columns=["Date", "Account ID"])
        self.assertEqual(1, len(current))
        self.assertEqual("acc-1", current["Account ID"][0])

    def test_state_cache_removed_column_counter(self):
        t = self._setup_state_test("test-6")
        t.state_cache(self._df([("2020-01-01", 1.0), ("2020-02-01", 2.0)]))
        self.assertEqual(1, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_UPDATE_COLUMNS))
        self.assertEqual(2, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_PREVIOUS_COLUMNS))
        self.assertEqual(2, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_CURRENT_COLUMNS))

    def test_state_cache_multiple_new_columns(self):
        t = self._setup_state_test("test-2")
        update = pl.DataFrame({
            "Date": ["2020-01-01", "2020-02-01"],
            "Value": [1.0, 2.0],
            "ColA": [10.0, 20.0],
            "ColB": [100.0, 200.0],
        }).with_columns(pl.col("Date").str.to_date())
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
        t.state_cache(self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]),
                      key_columns=["Date", "Account ID"])
        t.reset_counters()
        update = pl.DataFrame({
            "Date": ["2026-01-01", "2026-01-01"],
            "Account ID": ["acc-1", "acc-2"],
            "Balance": [100.0, 200.0],
            "Notes": ["note-a", "note-b"],
        }).with_columns(pl.col("Date").str.to_date())
        delta, current, previous = t.state_cache(update, key_columns=["Date", "Account ID"])
        self.assertIn("Notes", current.columns)
        self.assertIn("Notes", previous.columns)
        self.assertIsNone(previous.sort(["Date", "Account ID"])["Notes"][0])
        self.assertEqual(["note-a", "note-b"], current.sort(["Date", "Account ID"])["Notes"].to_list())
        self.assertEqual(2, len(delta))

    def test_state_cache_multi_key_removed_column(self):
        t = self._setup_state_test("mk-15")
        initial = pl.DataFrame({
            "Date": ["2026-01-01", "2026-01-01"],
            "Account ID": ["acc-1", "acc-2"],
            "Balance": [100.0, 200.0],
            "Notes": ["note-a", "note-b"],
        }).with_columns(pl.col("Date").str.to_date())
        t.state_cache(initial, key_columns=["Date", "Account ID"])
        t.reset_counters()
        delta, current, previous = t.state_cache(
            self._multi_key_dataframe([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]),
            key_columns=["Date", "Account ID"])
        self.assertIn("Notes", current.columns)
        self.assertIsNone(current.sort(["Date", "Account ID"])["Notes"][0])
        self.assertEqual("note-a", previous.sort(["Date", "Account ID"])["Notes"][0])
        self.assertEqual(2, len(delta))
        self.assertIsNone(delta.sort(["Date", "Account ID"])["Notes"][0])

    def test_state_cache_coalesce_preserves_current_when_update_null(self):
        t = self._setup_state_test("sc-1")
        first = pl.DataFrame({
            "Date": ["2024-01-01", "2024-01-02"],
            "Value": [1.0, 2.0],
            "Extra": [10.0, 20.0],
        }).with_columns(pl.col("Date").str.to_date())
        t.state_cache(first)
        t.reset_counters()
        update = pl.DataFrame({
            "Date": ["2024-01-02", "2024-01-03"],
            "Value": [None, 3.0],
            "Extra": [None, 30.0],
        }).with_columns(pl.col("Date").str.to_date())
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
        return pl.DataFrame({
            "Date": [p[0] for p in date_value_pairs],
            "Value": [float(p[1]) for p in date_value_pairs],
        }).with_columns(pl.col("Date").str.to_date())

    def run_plugin(self, plugin_name, repo_scope=plugin.RepoScope.LOCAL, test_name="replete_1", prepare_only=False, log_level="info",
                   disable_sheet_downloads=False, disable_database_downloads=False, disable_drive_downloads=False, disable_source_downloads=False,
                   disable_sheet_uploads=True, disable_database_uploads=True, disable_drive_uploads=True,
                   enable_rerun=True, force_reprocessing=False, force_downloads=False,
                   counter_asserts=None, custom_asserts=None, file_asserts=None):
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
        plugin.database_close()
        os.environ['WRANGLE_DATABASE_HOST'] = os.environ['POSTGRES_IP_PROD']
        plugin.database_open()
        dir_target = join(DIR_ROOT, "target")
        if not isdir(dir_target):
            os.makedirs(dir_target)
        plugin_module = getattr(importlib.import_module(f"wrangle.plugin.{plugin_name}"), plugin_name.title())()
        print("", flush=True)
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
                plugin_module.reset_counters()
                _print("STARTING (rerun)")
                plugin_module.run()
                _print("FINISHED (rerun)")
                self._save_pass_snapshot(plugin_module, 2)
                noop_counters = plugin_module.get_counters()
                _print("STARTING (assert)")
                assert_started = time.time()
                print_log("Assert", "Starting ...")
                self._assert_counters(noop_counters, ASSERT_NOOP)
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
                self._assert_counters(reload_counters, ASSERT_RELOAD)
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
                self._assert_customs(custom_asserts, first_counters, second_counters, reload_counters)
                print_log("Assert", f"Finished in [{time.time() - assert_started:.3f}] sec")
                _print("FINISHED (assert)")

    def _save_pass_snapshot(self, plugin_module, pass_number):
        suffix_map = {1: "_1_run", 2: "_2_rerun", 3: "_3_reprocess"}
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
                    assert_fn(actual_value, expected,
                              f"Counter [{counter_source} {counter_action}] {label} assertion failed [{actual_value}] {op} [{expected}]")
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

    def _assert_customs(self, assertions, first, second, third):
        for custom_assert in assertions:
            started = time.time()
            result = custom_assert(first, second, third)
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
        print("", flush=True)
        _load_csv.cache_clear()
        shutil.rmtree(join(DIR_ROOT, "target", "data"), ignore_errors=True)
        os.makedirs(join(DIR_ROOT, "target", "data"))
        shutil.rmtree(join(DIR_ROOT, "target", "runtime-unit"), ignore_errors=True)
        os.makedirs(join(DIR_ROOT, "target", "runtime-unit"))
        reset_config(log="info")

    def tearDown(self):
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
    return name != 'Date' and dtype in _STR_DTYPES


def _first_true_index(mask_series: pl.Series | bool):
    if isinstance(mask_series, bool):
        return 0 if mask_series else None
    indices = mask_series.arg_true()
    return None if len(indices) == 0 else int(indices[0])


def _count_leading_zero_rows(csv_df, numeric_cols):
    if not numeric_cols:
        return 0
    mask = csv_df.select(
        pl.any_horizontal((pl.col(c) == 0) & pl.col(c).is_not_null() for c in numeric_cols).alias("z")
    )["z"]
    first_false = _first_true_index(~mask)
    return len(mask) if first_false is None else int(first_false)


def _count_trailing_zero_rows(csv_df, numeric_cols):
    if not numeric_cols:
        return 0
    mask = csv_df.select(
        pl.any_horizontal((pl.col(c) == 0) & pl.col(c).is_not_null() for c in numeric_cols).alias("z")
    )["z"]
    first_false_from_end = _first_true_index(~mask.reverse())
    return len(mask) if first_false_from_end is None else int(first_false_from_end)


def _count_leading_none_rows(csv_df, cols):
    if not cols:
        return 0
    mask = csv_df.select(
        pl.any_horizontal(pl.col(c).is_null() for c in cols).alias("n")
    )["n"]
    first_false = _first_true_index(~mask)
    return len(mask) if first_false is None else int(first_false)


def _count_trailing_none_rows(csv_df, cols):
    if not cols:
        return 0
    mask = csv_df.select(
        pl.any_horizontal(pl.col(c).is_null() for c in cols).alias("n")
    )["n"]
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
            violations = csv_df.select([
                (pl.col(c).is_null() & pl.col(c).is_not_null().cast(pl.UInt32).cum_sum().gt(0)).sum().alias(c)
                for c in cols
            ])
        elif after_last_rows:
            violations = csv_df.select([
                (pl.col(c).is_null() & pl.col(c).is_not_null().reverse().cast(pl.UInt32).cum_sum().reverse().gt(0)).sum().alias(c)
                for c in cols
            ])
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
        numeric_cols = [col for col in _filter_cols(csv_df, include, exclude) if csv_df.schema[col] in _NUMERIC_DTYPES]
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
        numeric_cols = [col for col in _filter_cols(csv_df, include, exclude) if csv_df.schema[col] in _NUMERIC_DTYPES]
        if not numeric_cols:
            return None
        if after_first_rows:
            violations = csv_df.select([
                ((pl.col(c).eq(0) & pl.col(c).is_not_null()) &
                 (pl.col(c).ne(0) | pl.col(c).is_null()).cast(pl.UInt32).cum_sum().gt(0)).sum().alias(c)
                for c in numeric_cols
            ])
        elif after_last_rows:
            violations = csv_df.select([
                ((pl.col(c).eq(0) & pl.col(c).is_not_null()) &
                 (pl.col(c).ne(0) | pl.col(c).is_null()).reverse().cast(pl.UInt32).cum_sum().reverse().gt(0)).sum().alias(c)
                for c in numeric_cols
            ])
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


def assert_custom_rows_delta(equals=None, at_least=None, at_most=None):
    if equals is None and at_least is None and at_most is None:
        raise ValueError("assert_custom_rows_delta requires one of equals, at_least, or at_most")

    def _assert(first, _, third):
        current_rows = third.get(plugin.CTR_SRC_DATA, {}).get(plugin.CTR_ACT_CURRENT_ROWS, 0)
        previous_rows = first.get(plugin.CTR_SRC_DATA, {}).get(plugin.CTR_ACT_PREVIOUS_ROWS, 0)
        delta = current_rows - previous_rows
        _assert._last_delta = delta  # type: ignore
        if equals is not None and delta != equals:
            return f"assert_rows_delta: expected delta == {equals}, got {delta} (current_rows={current_rows}, previous_rows={previous_rows})"
        if at_least is not None and delta < at_least:
            return f"assert_rows_delta: expected delta > {at_least}, got {delta} (current_rows={current_rows}, previous_rows={previous_rows})"
        if at_most is not None and delta > at_most:
            return f"assert_rows_delta: expected delta < {at_most}, got {delta} (current_rows={current_rows}, previous_rows={previous_rows})"
        return None

    parts = [f"is_{equals}" if equals is not None else None,
             f"at_least_{at_least}" if at_least is not None else None,
             f"at_most_{at_most}" if at_most is not None else None]
    suffix = "_".join(p for p in parts if p is not None)
    _assert.last_delta = None  # type: ignore
    _assert._pass_values = lambda: [f"actual={_assert.last_delta}"]  # type: ignore
    _assert.__name__ = f"assert_custom_rows_delta_{suffix}" if suffix else "assert_custom_rows_delta"
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

for key, value in list(plugin.load_profile(join(DIR_ROOT, ".env")).items()):
    os.environ[key] = value


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
    plugin.database_close()


def drive_delete(drive_dir, file_name):
    if drive_dir is None or file_name is None:
        return
    credentials = google.oauth2.service_account.Credentials.from_service_account_file(
        get_file(".google_service_account.json"), scopes=['https://www.googleapis.com/auth/drive'])
    service = build('drive', 'v3', credentials=credentials, cache_discovery=False)
    token = None
    drive_file_id = None
    while True:
        response = service.files().list(
            q=f"'{drive_dir}' in parents and name = '{file_name}' and trashed = false",
            spaces='drive',
            fields='nextPageToken, files(id, name)',
            pageToken=token
        ).execute()
        for drive_file in response.get('files', []):
            drive_file_id = drive_file["id"]
            break
        token = response.get('nextPageToken')
        if not token or drive_file_id is not None:
            break
    if drive_file_id is not None:
        service.files().delete(fileId=drive_file_id).execute()


class PluginStub(Plugin):
    def _run(self):
        pass

    def __init__(self, name, drive_folder):
        super().__init__(name, repos=plugin.Repos(
            preview={"drive_folder": "PLACEHOLDER"},
            release={"drive_folder": drive_folder},
        ))


def _load_fixture(scope: str, plugin_name: str, test_name: str) -> dict:
    path = join(DIR_ROOT, "src/test/resources/repos", scope, plugin_name, test_name, "fixture.toml")
    assert isfile(path), f"Fixture [{path}] not found, run [src/test/resources/repos/refresh.sh] to generate it"
    with open(path, "rb") as toml_file:
        fixture = tomllib.load(toml_file)
    cols_full = {
        "balances": len(CURRENCY_COLUMNS),
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
    sys.exit(pytest.main(["-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache", __file__, ]))
