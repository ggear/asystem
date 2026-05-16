import sys
from os.path import dirname

sys.path.insert(0, dirname(__file__))

import copy
import csv_diff
import filecmp
import functools
import datetime
import glob
import importlib
import os
import re
import shutil
import subprocess
import sys
import time
import unittest
from collections.abc import Iterable
from os.path import abspath, basename, dirname, isdir, isfile, join, realpath

import google.oauth2.service_account
import polars as pl
import pytest
from googleapiclient.discovery import build

sys.path.append('../../../main/python')

from wrangle import plugin
from wrangle.plugin.equity import REPOS_EQUITY, STOCK
from wrangle.plugin.balances import REPOS_BALANCES
from wrangle.plugin.interest import REPOS_INTEREST
from wrangle.plugin import Plugin, DownloadResult, DownloadStatus
from wrangle.plugin.currency import REPOS_CURRENCY
from wrangle.plugin.config import get_file
from wrangle.plugin.logger import dataframe_print, print_log

########################################################################################################################
# NOTES:
#   - Include in test runner templates for realtime, unbuffered output: PYTHONUNBUFFERED=1;JB_DISABLE_BUFFERING=1
########################################################################################################################


DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
_ASSERT_FILE_EQUAL_SEEN = set()
_COUNTER_COMPARATOR_VERBS = {
    "counter_equals": "is",
    "counter_less": "less_than",
    "counter_at_least": "at_least",
}
_ASSERT_PASS_COL = 60


def _to_slug(text):
    return text.lower().replace(" ", "_")


def _print_assert_pass(name, *values):
    actuals = [str(v)[7:] for v in values if str(v).startswith("actual=")]
    line = f"PASS [{name}]"
    if actuals:
        print(f"{line:<{_ASSERT_PASS_COL}}{'    ' + ' '.join(f'[{a}]' for a in actuals)}", flush=True)
    else:
        print(line, flush=True)


def _format_assert_elapsed(seconds):
    return f"{f'{seconds:.3f}'.rstrip('0').rstrip('.')}s"


def _first_true_index(mask_series: pl.Series | bool):
    if isinstance(mask_series, bool):
        return 0 if mask_series else None
    indices = mask_series.arg_true()
    return None if len(indices) == 0 else int(indices[0])


# noinspection PyMethodMayBeStatic
class WrangleTest(unittest.TestCase):

    ########################################################################################################################
    # Balances
    ########################################################################################################################

    # No current data, no new data, no remote source data downloads, no remote data repo downloads or uploads
    def test_balances_local_blank_1(self):
        self.run_plugin("balances", plugin.RepoScope.LOCAL, "blank_1", log_level="info",
                        disable_source_downloads=True, disable_sheet_downloads=True, disable_database_downloads=True,
                        disable_repo_downloads=True, disable_repo_uploads=True, enable_rerun=False, force_reprocessing=False,
                        counter_asserts=ASSERT_NONE,
                        file_asserts={
                            "__balances_current.csv": [
                                assert_file_does_not_exist(),
                            ],
                        })

    # No current data, corrupt data, no remote source data downloads, no remote data repo downloads or uploads
    @pytest.mark.skip(reason="requires update")
    def test_balances_local_corrupt_1(self):
        self.run_plugin("balances", plugin.RepoScope.LOCAL, "corrupt_1", log_level="fatal",
                        disable_source_downloads=True, disable_sheet_downloads=True, disable_database_downloads=True,
                        disable_repo_downloads=True, disable_repo_uploads=True, enable_rerun=False, force_reprocessing=True,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_ERRORED: 1,
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
    def test_balances_local_corrupt_2(self):
        self.run_plugin("balances", plugin.RepoScope.LOCAL, "corrupt_2", log_level="fatal",
                        disable_source_downloads=True, disable_sheet_downloads=True, disable_database_downloads=True,
                        disable_repo_downloads=True, disable_repo_uploads=True, enable_rerun=False, force_reprocessing=True,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_ERRORED: 1,
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
                        disable_source_downloads=True, disable_sheet_downloads=True, disable_database_downloads=True,
                        disable_repo_downloads=False, disable_repo_uploads=False, enable_rerun=True, force_reprocessing=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_SOURCES: {
                                    plugin.CTR_ACT_UPLOADED: 2,
                                },
                                plugin.CTR_SRC_DATA: {
                                    plugin.CTR_ACT_PREVIOUS_COLUMNS: 15,
                                    plugin.CTR_ACT_CURRENT_COLUMNS: 15,
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
                        disable_source_downloads=False, disable_sheet_downloads=False, disable_database_downloads=False,
                        disable_repo_downloads=False, disable_repo_uploads=True, enable_rerun=True, force_reprocessing=False,
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
        self.run_plugin("currency", plugin.RepoScope.LOCAL, "blank_1", log_level="info",
                        disable_source_downloads=True, disable_sheet_downloads=True, disable_database_downloads=True,
                        disable_repo_downloads=True, disable_repo_uploads=True, enable_rerun=False, force_reprocessing=False,
                        counter_asserts=ASSERT_NONE,
                        file_asserts={
                            "__currency_current.csv": [
                                assert_file_does_not_exist(),
                            ],
                        })

    # No current data, corrupt data, no remote source data downloads, no remote data repo downloads or uploads
    def test_currency_local_corrupt_1(self):
        self.run_plugin("currency", plugin.RepoScope.LOCAL, "corrupt_1", log_level="fatal",
                        disable_source_downloads=True, disable_sheet_downloads=True, disable_database_downloads=True,
                        disable_repo_downloads=True, disable_repo_uploads=True, enable_rerun=False, force_reprocessing=True,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_ERRORED: 1,
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
        self.run_plugin("currency", plugin.RepoScope.LOCAL, "corrupt_2", log_level="fatal",
                        disable_source_downloads=True, disable_sheet_downloads=True, disable_database_downloads=True,
                        disable_repo_downloads=True, disable_repo_uploads=True, enable_rerun=False, force_reprocessing=True,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_ERRORED: 1,
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
        drive_delete(REPOS_CURRENCY._scopes["preview"]["drive_folder"], "rba_fx_1987-1990.xls")
        drive_delete(REPOS_CURRENCY._scopes["preview"]["drive_folder"], "rba_fx_2023-current.xls")
        self.run_plugin("currency", plugin.RepoScope.PREVIEW, "replete_1", log_level="info",
                        disable_source_downloads=True, disable_sheet_downloads=True, disable_database_downloads=True,
                        disable_repo_downloads=False, disable_repo_uploads=False, enable_rerun=True, force_reprocessing=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_SOURCES: {
                                    plugin.CTR_ACT_UPLOADED: 2,
                                },
                                plugin.CTR_SRC_DATA: {
                                    plugin.CTR_ACT_PREVIOUS_COLUMNS: 15,
                                    plugin.CTR_ACT_CURRENT_COLUMNS: 15,
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
                            "__currency_current.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="1983-12-12", end_date="2024-10-14", contiguous="days"),
                                assert_file_nones_per_row(),
                                assert_file_zeroes_per_col(exclude=r"Delta"),
                            ],
                            "_sheet_rates_currency.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="2006-01-02", end_date="2024-10-14", contiguous="days", descending=True),
                                assert_file_nones_per_row(),
                                assert_file_zeroes_per_row(),
                            ],
                            "_database_currency.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="1983-12-12", end_date="2024-10-14", contiguous="days"),
                                assert_file_nones_per_row(),
                            ],
                        })

    # Lots of current data, a lot of live new data, downloads from remote sources, downloads from release data repo, no remote data repo uploads
    def test_currency_release_replete_1(self):
        self.run_plugin("currency", plugin.RepoScope.RELEASE, "replete_1", log_level="info",
                        disable_source_downloads=False, disable_sheet_downloads=False, disable_database_downloads=False,
                        disable_repo_downloads=False, disable_repo_uploads=True, enable_rerun=True, force_reprocessing=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_DATA: {
                                    plugin.CTR_ACT_PREVIOUS_COLUMNS: 15,
                                    plugin.CTR_ACT_CURRENT_COLUMNS: 15,
                                    plugin.CTR_ACT_UPDATE_COLUMNS: 15,
                                    plugin.CTR_ACT_DELTA_COLUMNS: 15,
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
                            "__currency_current*.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="1983-12-12", contiguous="days"),
                                assert_file_nones_per_row(),
                                assert_file_zeroes_per_col(exclude=r"Delta"),
                                assert_file_equal(),
                            ],
                            "_sheet_rates_currency*.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="2006-01-02", contiguous="days", descending=True),
                                assert_file_nones_per_row(),
                                assert_file_zeroes_per_row(),
                                assert_file_equal(),
                            ],
                            "_database_currency*.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="1983-12-12", contiguous="days"),
                                assert_file_nones_per_row(),
                                assert_file_equal(),
                            ],
                        })

    ########################################################################################################################
    # Equity
    ########################################################################################################################

    # No current data, no new data, no remote source data downloads, no remote data repo downloads or uploads
    def test_equity_local_blank_1(self):
        self.run_plugin("equity", plugin.RepoScope.LOCAL, "blank_1", log_level="info",
                        disable_source_downloads=True, disable_sheet_downloads=True, disable_database_downloads=True,
                        disable_repo_downloads=True, disable_repo_uploads=True, enable_rerun=False, force_reprocessing=False,
                        counter_asserts=ASSERT_NONE,
                        file_asserts={
                            "__equity_current.csv": [
                                assert_file_does_not_exist(),
                            ],
                        })

    # No current data, corrupt data, no remote source data downloads, no remote data repo downloads or uploads
    def test_equity_local_corrupt_1(self):
        self.run_plugin("equity", plugin.RepoScope.LOCAL, "corrupt_1", log_level="fatal",
                        disable_source_downloads=True, disable_sheet_downloads=True, disable_database_downloads=True,
                        disable_repo_downloads=True, disable_repo_uploads=True, enable_rerun=False, force_reprocessing=True,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_ERRORED: 1,
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
        self.run_plugin("equity", plugin.RepoScope.LOCAL, "corrupt_2", log_level="debug",
                        disable_source_downloads=True, disable_sheet_downloads=True, disable_database_downloads=True,
                        disable_repo_downloads=True, disable_repo_uploads=True, enable_rerun=False, force_reprocessing=True,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_ERRORED: 1,
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
        self.run_plugin("equity", plugin.RepoScope.LOCAL, "partial_1", log_level="info",
                        disable_source_downloads=True, disable_sheet_downloads=True, disable_database_downloads=True,
                        disable_repo_downloads=True, disable_repo_uploads=True, enable_rerun=False, force_reprocessing=True,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_PROCESSED: 3,
                                },
                                plugin.CTR_SRC_DATA: {
                                    plugin.CTR_ACT_PREVIOUS_COLUMNS: 34,
                                    plugin.CTR_ACT_CURRENT_COLUMNS: 34,
                                    plugin.CTR_ACT_UPDATE_COLUMNS: 34,
                                    plugin.CTR_ACT_DELTA_COLUMNS: 34,
                                    plugin.CTR_ACT_DELTA_ROWS: 2193,
                                },
                            },
                        }),
                        file_asserts={
                            "__equity_current.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="2019-12-31", end_date="2025-12-31", contiguous="days"),
                                assert_file_nones_per_col(after_first_rows=True),
                                assert_file_zeroes_per_row(exclude=r"Market Volume|Change"),
                            ],
                            "_sheet_prices_history.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="2019-12-31", end_date="2025-12-31", contiguous="days", descending=True),
                                assert_file_nones_per_col(after_last_rows=True),
                                assert_file_zeroes_per_row(),
                            ],
                            "_database_equity.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="2019-12-31", end_date="2025-12-31", contiguous="days"),
                                assert_file_nones_per_col(after_first_rows=True),
                            ],
                        })

    # Lots of current data, a specific amount of new data, no remote source data downloads, no remote data repo downloads or uploads
    def test_equity_local_partial_2(self):
        self.run_plugin("equity", plugin.RepoScope.LOCAL, "partial_2", log_level="info",
                        disable_source_downloads=True, disable_sheet_downloads=True, disable_database_downloads=True,
                        disable_repo_downloads=True, disable_repo_uploads=True, enable_rerun=False, force_reprocessing=True,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_PROCESSED: 1,
                                },
                                plugin.CTR_SRC_DATA: {
                                    plugin.CTR_ACT_PREVIOUS_COLUMNS: 17,
                                    plugin.CTR_ACT_CURRENT_COLUMNS: 17,
                                    plugin.CTR_ACT_UPDATE_COLUMNS: 17,
                                    plugin.CTR_ACT_DELTA_COLUMNS: 17,
                                    plugin.CTR_ACT_DELTA_ROWS: 29,
                                },
                            },
                        }),
                        file_asserts={
                            "__equity_current.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="2025-01-02", end_date="2025-01-30", contiguous="days"),
                                assert_file_nones_per_col(after_first_rows=True),
                                assert_file_zeroes_per_row(exclude=r"Market Volume|Change"),
                            ],
                            "_sheet_prices_history.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="2025-01-02", end_date="2025-01-30", contiguous="days", descending=True),
                                assert_file_nones_per_col(after_last_rows=True),
                                assert_file_zeroes_per_row(),
                            ],
                            "_database_equity.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="2025-01-02", end_date="2025-01-30", contiguous="days"),
                                assert_file_nones_per_col(after_first_rows=True),
                            ],
                        })

    # Lots of current data, a specific amount of new data, no remote source data downloads, no remote data repo downloads or uploads
    def test_equity_local_partial_3(self):
        self.run_plugin("equity", plugin.RepoScope.LOCAL, "partial_3", log_level="info",
                        disable_source_downloads=True, disable_sheet_downloads=True, disable_database_downloads=True,
                        disable_repo_downloads=True, disable_repo_uploads=True, enable_rerun=False, force_reprocessing=True,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_PROCESSED: 1,
                                },
                                plugin.CTR_SRC_DATA: {
                                    plugin.CTR_ACT_PREVIOUS_COLUMNS: 17,
                                    plugin.CTR_ACT_CURRENT_COLUMNS: 17,
                                    plugin.CTR_ACT_UPDATE_COLUMNS: 17,
                                    plugin.CTR_ACT_DELTA_COLUMNS: 17,
                                    plugin.CTR_ACT_DELTA_ROWS: 29,
                                },
                            },
                        }),
                        file_asserts={
                            "__equity_current.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="2025-01-02", end_date="2025-01-30", contiguous="days"),
                                assert_file_nones_per_col(after_first_rows=True),
                                assert_file_zeroes_per_row(exclude=r"Market Volume|Change"),
                            ],
                            "_sheet_prices_history.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="2025-01-02", end_date="2025-01-30", contiguous="days", descending=True),
                                assert_file_nones_per_col(after_last_rows=True),
                                assert_file_zeroes_per_row(),
                            ],
                            "_database_equity.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="2025-01-02", end_date="2025-01-30", contiguous="days"),
                                assert_file_nones_per_col(after_first_rows=True),
                            ],
                        })

    # Lots of current data, a specific amount of new data, no remote source data downloads, no remote data repo downloads or uploads
    def test_equity_local_replete_1(self):
        self.run_plugin("equity", plugin.RepoScope.LOCAL, "replete_1", log_level="info",
                        disable_source_downloads=True, disable_sheet_downloads=True, disable_database_downloads=True,
                        disable_repo_downloads=True, disable_repo_uploads=True, enable_rerun=False, force_reprocessing=True,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_PROCESSED: 480,
                                },
                                plugin.CTR_SRC_DATA: {
                                    plugin.CTR_ACT_PREVIOUS_COLUMNS: 408,
                                    plugin.CTR_ACT_CURRENT_COLUMNS: 408,
                                    plugin.CTR_ACT_UPDATE_COLUMNS: 408,
                                    plugin.CTR_ACT_DELTA_COLUMNS: 408,
                                    plugin.CTR_ACT_DELTA_ROWS: 15094,
                                },
                            },
                        }),
                        file_asserts={
                            "__equity_current.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="1985-01-02", end_date="2026-04-30", contiguous="days"),
                                assert_file_nones_per_col(after_first_rows=True),
                                assert_file_zeroes_per_row(exclude=r"Market Volume|Change"),
                            ],
                            "_sheet_prices_history.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="2007-01-01", end_date="2026-04-30", contiguous="days", descending=True),
                                assert_file_nones_per_col(after_last_rows=True),
                                assert_file_zeroes_per_row(),
                            ],
                            "_database_equity.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="1985-01-02", end_date="2026-04-30", contiguous="days"),
                                assert_file_nones_per_col(after_first_rows=True),
                            ],
                        })

    # Lots of current data, a specific amount of new data, no remote source data downloads, downloads and uploads from and to preview data repo
    def test_equity_preview_replete_1(self):
        drive_delete(REPOS_EQUITY._scopes["preview"]["drive_folder"], "yahoo_acdc_2018.csv")
        self.run_plugin("equity", plugin.RepoScope.PREVIEW, "replete_1", log_level="info",
                        disable_source_downloads=True, disable_sheet_downloads=True, disable_database_downloads=True,
                        disable_repo_downloads=False, disable_repo_uploads=False, enable_rerun=True, force_reprocessing=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_SOURCES: {
                                    plugin.CTR_ACT_UPLOADED: 1,
                                },
                                plugin.CTR_SRC_DATA: {
                                    plugin.CTR_ACT_PREVIOUS_COLUMNS: 425,
                                    plugin.CTR_ACT_CURRENT_COLUMNS: 425,
                                    plugin.CTR_ACT_UPDATE_COLUMNS: 0,
                                    plugin.CTR_ACT_DELTA_COLUMNS: 0,
                                    plugin.CTR_ACT_DELTA_ROWS: 0,
                                },
                            },
                        }),
                        custom_asserts=[
                            assert_custom_rows_delta(equals=1)
                        ],
                        file_asserts={
                            "__equity_current.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="1985-01-02", end_date="2026-04-30", contiguous="days"),
                                assert_file_nones_per_col(after_first_rows=True),
                                assert_file_zeroes_per_row(exclude=r"Market Volume|Change"),
                            ],
                            "_sheet_prices_history.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="2007-01-01", end_date="2026-04-30", contiguous="days", descending=True),
                                assert_file_nones_per_col(after_last_rows=True),
                                assert_file_zeroes_per_row(),
                            ],
                            "_database_equity.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="1985-01-02", end_date="2026-04-30", contiguous="days"),
                                assert_file_nones_per_col(after_first_rows=True),
                            ],
                        })

    # Lots of current data, a lot of live new data, downloads from remote sources, downloads from release data repo, no remote data repo uploads
    def test_equity_release_replete_1(self):
        self.run_plugin("equity", plugin.RepoScope.RELEASE, "replete_1", log_level="info",

                        # TODO: Restore once database/sheets provisioned
                        disable_source_downloads=False, disable_sheet_downloads=True, disable_database_downloads=True,
                        # disable_source_downloads=False, disable_sheet_downloads=False, disable_database_downloads=False,

                        disable_repo_downloads=False, disable_repo_uploads=True, enable_rerun=True, force_reprocessing=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_DATA: {
                                    plugin.CTR_ACT_PREVIOUS_COLUMNS: 425,
                                    plugin.CTR_ACT_CURRENT_COLUMNS: 425,
                                    plugin.CTR_ACT_UPDATE_COLUMNS: 425,
                                    plugin.CTR_ACT_DELTA_COLUMNS: 425,
                                },
                            },
                            "counter_at_least": {
                                plugin.CTR_SRC_SOURCES: {
                                    plugin.CTR_ACT_DOWNLOADED: len(STOCK),
                                },
                                plugin.CTR_SRC_DATA: {
                                    plugin.CTR_ACT_DELTA_ROWS: 1,
                                },
                            },
                        }),
                        custom_asserts=[
                            assert_custom_rows_delta(at_least=1)
                        ],
                        file_asserts={
                            "__equity_current*.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="1985-01-02", contiguous="days"),
                                assert_file_nones_per_col(after_first_rows=True),
                                assert_file_zeroes_per_row(exclude=r"Market Volume|Change"),
                                assert_file_equal(),
                            ],
                            "_sheet_prices_history*.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="2007-01-01", contiguous="days", descending=True),
                                assert_file_nones_per_col(after_last_rows=True),
                                assert_file_zeroes_per_row(),
                                assert_file_equal(),
                            ],
                            "_database_equity*.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="1985-01-02", contiguous="days"),
                                assert_file_nones_per_col(after_first_rows=True),
                                assert_file_equal(),
                            ],
                        })

    ########################################################################################################################
    # Interest
    ########################################################################################################################

    # No current data, no new data, no remote source data downloads, no remote data repo downloads or uploads
    def test_interest_local_blank_1(self):
        self.run_plugin("interest", plugin.RepoScope.LOCAL, "blank_1", log_level="info",
                        disable_source_downloads=True, disable_sheet_downloads=True, disable_database_downloads=True,
                        disable_repo_downloads=True, disable_repo_uploads=True, enable_rerun=False, force_reprocessing=False,
                        counter_asserts=ASSERT_NONE,
                        file_asserts={
                            "__interest_current.csv": [
                                assert_file_does_not_exist(),
                            ],
                        })

    # No current data, corrupt data, no remote source data downloads, no remote data repo downloads or uploads
    def test_interest_local_corrupt_1(self):
        self.run_plugin("interest", plugin.RepoScope.LOCAL, "corrupt_1", log_level="fatal",
                        disable_source_downloads=True, disable_sheet_downloads=True, disable_database_downloads=True,
                        disable_repo_downloads=True, disable_repo_uploads=True, enable_rerun=False, force_reprocessing=True,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_ERRORED: 1,
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
        self.run_plugin("interest", plugin.RepoScope.LOCAL, "corrupt_2", log_level="fatal",
                        disable_source_downloads=True, disable_sheet_downloads=True, disable_database_downloads=True,
                        disable_repo_downloads=True, disable_repo_uploads=True, enable_rerun=False, force_reprocessing=True,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_FILES: {
                                    plugin.CTR_ACT_ERRORED: 1,
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
        drive_delete(REPOS_INTEREST._scopes["preview"]["drive_folder"], "inflation.xlsx")
        self.run_plugin("interest", plugin.RepoScope.PREVIEW, "replete_1", log_level="info",
                        disable_source_downloads=True, disable_sheet_downloads=True, disable_database_downloads=True,
                        disable_repo_downloads=False, disable_repo_uploads=False, enable_rerun=True, force_reprocessing=False,
                        counter_asserts=merge_asserts(ASSERT_RUN, {
                            "counter_equals": {
                                plugin.CTR_SRC_SOURCES: {
                                    plugin.CTR_ACT_UPLOADED: 1,
                                },
                                plugin.CTR_SRC_DATA: {
                                    plugin.CTR_ACT_PREVIOUS_COLUMNS: 18,
                                    plugin.CTR_ACT_CURRENT_COLUMNS: 18,
                                    plugin.CTR_ACT_UPDATE_COLUMNS: 0,
                                    plugin.CTR_ACT_DELTA_COLUMNS: 0,
                                    plugin.CTR_ACT_DELTA_ROWS: 0,
                                },
                            },
                        }),
                        custom_asserts=[
                            assert_custom_rows_delta(equals=16)
                        ],
                        file_asserts={
                            "__interest_current.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="1982-04-01", end_date="2026-04-01", contiguous="months"),
                                assert_file_nones_per_row(exclude=r"Mean"),
                            ],
                            "_sheet_rates_interest.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="2015-02-01", end_date="2026-04-01", contiguous="months", descending=True),
                                assert_file_nones_per_row(exclude=r"Mean"),
                            ],
                            "_database_interest.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="1982-04-01", end_date="2026-04-01", contiguous="months"),
                                assert_file_nones_per_row(exclude=r"type=mean"),
                            ],
                        })

    # Lots of current data, a lot of live new data, downloads from remote sources, downloads from release data repo, no remote data repo uploads
    def test_interest_release_replete_1(self):
        self.run_plugin("interest", plugin.RepoScope.RELEASE, "replete_1", log_level="info",
                        disable_source_downloads=False, disable_sheet_downloads=False, disable_database_downloads=False,
                        disable_repo_downloads=False, disable_repo_uploads=True, enable_rerun=True, force_reprocessing=False,
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
                                    plugin.CTR_ACT_DELTA_ROWS: 16,
                                },
                            },
                        }),
                        custom_asserts=[
                            assert_custom_rows_delta(at_least=16)
                        ],
                        file_asserts={
                            "__interest_current*.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="1982-04-01", end_date="2026-04-01", contiguous="months"),
                                assert_file_nones_per_row(exclude=r"Mean"),
                                assert_file_equal(),
                            ],
                            "_sheet_rates_interest*.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="2015-02-01", end_date="2026-04-01", contiguous="months", descending=True),
                                assert_file_nones_per_row(exclude=r"Mean"),
                                assert_file_equal(),
                            ],
                            "_database_interest*.csv": [
                                assert_file_size(),
                                assert_file_dates(start_date="1982-04-01", end_date="2026-04-01", contiguous="months"),
                                assert_file_nones_per_row(exclude=r"type=mean"),
                                assert_file_equal(),
                            ],
                        })

    ########################################################################################################################
    # Sources
    ########################################################################################################################

    @pytest.mark.skip(reason="very slow")
    def test_library_sheet(self):
        test = PluginStub("Test", "SOME_NON_EXISTANT_GUID")

        def _sheet_read(_result, schema=None):
            if schema is None:
                schema = {}
            if _result.status == DownloadStatus.FAILED:
                return test.dataframe_new()
            return test.csv_read(_result.file_path, schema=schema)

        missing_name = "missing"
        missing_key = "!"
        missing_str = "[]"
        plugin.config.log_level = "fatal"
        for result in [
            test.sheet_download(missing_key, missing_name, sheet_load_secs=0, sheet_retry_max=1, write_cache=True),
            test.sheet_download(missing_key, missing_name, sheet_load_secs=0, sheet_retry_max=1, write_cache=False),
            test.sheet_download(missing_key, missing_name, sheet_load_secs=0, sheet_retry_max=1, write_cache=True),
            test.sheet_download(missing_key, missing_name, sheet_load_secs=0, sheet_retry_max=1, read_cache=False, write_cache=True),
        ]:
            data_df = _sheet_read(result)
            self.assertEqual(missing_str, test.dataframe_to_str(data_df))
            self.assertEqual(0, len(data_df))

        loading_name = "loading"
        loading_key = "1bUpZCIOM-olcxLQ7_fdgi4Nu7GOQC30sK_LALZ2B0bs"
        loading_str = "[]"
        plugin.config.log_level = "fatal"
        for result in [
            test.sheet_download(loading_key, loading_name, sheet_load_secs=0, sheet_retry_max=1, write_cache=True),
            test.sheet_download(loading_key, loading_name, sheet_load_secs=0, sheet_retry_max=1, write_cache=False),
            test.sheet_download(loading_key, loading_name, sheet_load_secs=0, sheet_retry_max=1, write_cache=True),
            test.sheet_download(loading_key, loading_name, sheet_load_secs=0, sheet_retry_max=1, read_cache=False, write_cache=True),
        ]:
            data_df = _sheet_read(result)
            self.assertEqual(loading_str, test.dataframe_to_str(data_df))
            self.assertEqual(0, len(data_df))

        empty_name = "empty"
        empty_key = "1nPtCOciS81Y-FWJZ8pi5-9Fd6RZ6_EqyfweBekFH6s4"
        test_column = {
            "My Column": pl.Utf8,
        }
        empty_str = "[]"
        empty_str_column = "[]"
        plugin.config.log_level = "info"
        for result in [
            test.sheet_download(empty_key, empty_name, write_cache=True),
            test.sheet_download(empty_key, empty_name, write_cache=False),
            test.sheet_download(empty_key, empty_name, write_cache=True),
            test.sheet_download(empty_key, empty_name, read_cache=False, write_cache=False),
        ]:
            data_df = _sheet_read(result)
            self.assertEqual(empty_str, test.dataframe_to_str(data_df))
            self.assertEqual(0, len(data_df))
        for result in [
            test.sheet_download(empty_key, empty_name, write_cache=True),
            test.sheet_download(empty_key, empty_name, write_cache=False),
            test.sheet_download(empty_key, empty_name, write_cache=True),
            test.sheet_download(empty_key, empty_name, read_cache=False, write_cache=True),
        ]:
            data_df = _sheet_read(result, schema=test_column)
            self.assertEqual(empty_str_column, test.dataframe_to_str(data_df))
            self.assertEqual(0, len(data_df))

        test_name = "test"
        test_key = "18MBAIWaQNVQBMESAISHIqLD11sRBz003x5OTH_Vt4SY"
        test_type_utf = {
            "Integer": pl.Utf8,
            "Integer with NULL": pl.Utf8,
            "Float": pl.Utf8,
            "Float with NULL": pl.Utf8,
            "String": pl.Utf8,
            "String with NULL": pl.Utf8,
        }
        test_type_number = {
            "Integer": pl.Int64,
            "Integer with NULL": pl.Int64,
            "Float": pl.Float64,
            "Float with NULL": pl.Float64,
            "String": pl.Utf8,
            "String with NULL": pl.Utf8,
        }
        test_str = "[Integer({}), Integer with NULL({}), Float({}), Float with NULL({}), String({}), String with NULL({})]"
        test_str_utf = ["String" for _ in range(0, len(test_type_number))]
        test_str_numeric = [test.dataframe_type_to_str(dtype) for dtype in test_type_number.values()]
        plugin.config.log_level = "info"
        for result in [
            test.sheet_download(test_key, test_name + "-1", sheet_start_row=3, write_cache=True),
            test.sheet_download(test_key, test_name + "-1", sheet_start_row=3, write_cache=False),
            test.sheet_download(test_key, test_name + "-1", sheet_start_row=3, write_cache=True),
            test.sheet_download(test_key, test_name + "-1", sheet_start_row=3, read_cache=False, write_cache=True),
            test.sheet_download(test_key, test_name + "-2", sheet_start_row=3, write_cache=True),
            test.sheet_download(test_key, test_name + "-2", sheet_start_row=3, write_cache=False),
            test.sheet_download(test_key, test_name + "-2", sheet_start_row=3, write_cache=True),
            test.sheet_download(test_key, test_name + "-2", sheet_start_row=3, read_cache=False, write_cache=True),
        ]:
            data_df = _sheet_read(result, schema=test_type_number)
            self.assertEqual(test_str.format(*test_str_numeric), test.dataframe_to_str(data_df))
            self.assertEqual(4, len(data_df))
        for result in [
            test.sheet_download(test_key, test_name + "-3", sheet_start_row=3, write_cache=True),
            test.sheet_download(test_key, test_name + "-3", sheet_start_row=3, write_cache=False),
            test.sheet_download(test_key, test_name + "-3", sheet_start_row=3, write_cache=True),
            test.sheet_download(test_key, test_name + "-3", sheet_start_row=3, read_cache=False, write_cache=True),
        ]:
            data_df = _sheet_read(result, schema=test_type_utf)
            self.assertEqual(test_str.format(*test_str_utf), test.dataframe_to_str(data_df))
            self.assertEqual(4, len(data_df))

        data_name = "Index_weights"
        data_key = "1Kf9-Gk7aD4aBdq2JCfz5zVUMWAtvJo2ZfqmSQyo8Bjk"
        data_type = {
            "Holdings Quantity": pl.Utf8,
        }
        data_str = "[Exchange Symbol(String), Holdings Quantity({}), Unit Price(Float64), Watch Value(Float64), Watch Quantity(Int64), Baseline Quantity(Float64)]"
        data_str_type = [test.dataframe_type_to_str(data_type[column]) for column in data_type]
        for result in [
            test.sheet_download(data_key, data_name + "-1", "Indexes", 2, write_cache=True),
            test.sheet_download(data_key, data_name + "-1", "Indexes", 2, write_cache=False),
            test.sheet_download(data_key, data_name + "-1", "Indexes", 2, write_cache=True),
            test.sheet_download(data_key, data_name + "-1", "Indexes", 2, read_cache=False, write_cache=True),
        ]:
            data_df = _sheet_read(result)
            self.assertEqual(data_str.format("Float64"), test.dataframe_to_str(data_df))
            self.assertEqual(26, len(data_df))
        for result in [
            test.sheet_download(data_key, data_name + "-1", "Indexes", 2, write_cache=True),
            test.sheet_download(data_key, data_name + "-1", "Indexes", 2, write_cache=False),
            test.sheet_download(data_key, data_name + "-1", "Indexes", 2, write_cache=True),
            test.sheet_download(data_key, data_name + "-1", "Indexes", 2, read_cache=False, write_cache=True),
        ]:
            data_df = _sheet_read(result, schema=data_type)
            self.assertEqual(data_str.format(*data_str_type), test.dataframe_to_str(data_df))
            self.assertEqual(26, len(data_df))

    def test_library_database(self):
        from datetime import date as date_type

        test = PluginStub("Test", "SOME_NON_EXISTANT_GUID")
        reset_config()
        csv_path = abspath(f"{test.local_cache}/_database_test.csv")

        invalid_cache = "Invalid"
        invalid_path = abspath(f"{test.local_cache}/_database_{invalid_cache.lower()}.csv")
        for result in [
            test.database_download(invalid_cache, "SELECT 1", force=True),
            test.database_download(invalid_cache, "SELECT 1", force=False),
            test.database_download(invalid_cache, "SELECT 1", check=False, force=True),
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
        self.assertEqual(3, len((test.dataframe_new(df_data, schema={column: pl.Utf8 for column in df_data[0]}))))

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
        self.assertEqual(df_lots_rows, len((test.dataframe_new(df_lots))))
        self.assertEqual(df_lots_rows, len((test.dataframe_new(df_lots, schema={"SOME UNKNOWN COLUMN": pl.Utf8}))))
        self.assertEqual(df_lots_rows, len((test.dataframe_new(df_lots, schema={column: pl.Utf8 for column in df_data[0]}))))
        self.assertEqual(df_lots_rows, len((test.dataframe_new(df_lots, schema={column: pl.Utf8 for column in df_lots[0]}))))

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
            str_cols = [c for c, t in zip(df.columns, df.dtypes) if _is_string_col(c, t)]
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
            str_cols = [_c for _c, _t in zip(df.columns, df.dtypes) if _is_string_col(_c, _t)]
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
            str_cols = [_c for _c, _t in zip(df.columns, df.dtypes) if _is_string_col(_c, _t)]
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
            str_cols = [_c for _c, _t in zip(df.columns, df.dtypes) if _is_string_col(_c, _t)]
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
        src = join(DIR_ROOT, "src/test/resources/state", fixture)
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

    def run_plugin(self, plugin_name, repo_scope=plugin.RepoScope.LOCAL, test_name="replete_1",
                   log_level="info", prepare_only=False, enable_rerun=True,
                   force_reprocessing=False, force_downloads=False,
                   disable_source_downloads=False, disable_sheet_downloads=False, disable_database_downloads=False,
                   disable_repo_downloads=True, disable_repo_uploads=True,
                   counter_asserts=None, custom_asserts=None, file_asserts=None):
        global _ASSERT_PASS_COL
        if file_asserts is None:
            file_asserts = {}
        if custom_asserts is None:
            custom_asserts = []
        if not disable_repo_uploads and repo_scope == plugin.RepoScope.RELEASE:
            raise ValueError("Cannot enable uploads when repo_scope is RELEASE")
        plugin.config.log_level = log_level
        plugin.config.repo_scope = repo_scope
        plugin.config.force_reprocessing = force_reprocessing
        plugin.config.force_downloads = force_downloads
        plugin.config.disable_source_downloads = disable_source_downloads
        plugin.config.disable_sheet_downloads = disable_sheet_downloads
        plugin.config.disable_database_downloads = disable_database_downloads
        plugin.config.disable_repo_downloads = disable_repo_downloads
        plugin.config.disable_repo_uploads = disable_repo_uploads
        plugin.database_close()
        dir_target = join(DIR_ROOT, "target")
        if not isdir(dir_target):
            os.makedirs(dir_target)
        plugin_module = getattr(importlib.import_module(f"wrangle.plugin.{plugin_name}"), plugin_name.title())()
        print("", flush=True)
        self._load_caches(plugin_module, join(DIR_ROOT, "src/test/resources/repos", repo_scope, plugin_name, test_name))
        label = f"{{:<22}} {f'[{plugin_name.title()}]':<15}   {f'[{repo_scope.name}]':<10}   {f'[{test_name}]'}"
        _print = lambda stage: print(("\n" if stage.startswith("STARTING") else "") + label.format(stage) + ("\n" if stage.startswith("FINISHED") else ""), flush=True)
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
                    name = f"assert_counter_{_to_slug(counter_source)}_{_to_slug(counter_action)}_{verb}_{expected}"
                    _print_assert_pass(f"{name} ({_format_assert_elapsed(time.time() - started)})", f"actual={actual_value}")

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


_NUMERIC_DTYPES = (pl.Float32, pl.Float64, pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64)
_STR_DTYPES = (pl.String, pl.Utf8, pl.Null)


def _is_string_col(name, dtype):
    return name != 'Date' and dtype in _STR_DTYPES


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


@functools.lru_cache(maxsize=None)
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


def assert_file_dates(start_date=None, end_date=None, max_gap_days=1, descending=None, contiguous=None):
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
        elif descending is True:
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
        _assert._last_delta = delta
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
    _assert.last_delta = None
    _assert._pass_values = lambda: [f"actual={_assert.last_delta}"]
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
    "counter_equals": {
        plugin.CTR_SRC_SOURCES: {
            plugin.CTR_ACT_ERRORED: 0,
        },
        plugin.CTR_SRC_FILES: {
            plugin.CTR_ACT_ERRORED: 0,
        },
        plugin.CTR_SRC_DATA: {
            plugin.CTR_ACT_ERRORED: 0,
        },
        plugin.CTR_SRC_EGRESS: {
            plugin.CTR_ACT_ERRORED: 0,
        },
    },
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
            plugin.CTR_ACT_ERRORED: 0,
        },
        plugin.CTR_SRC_FILES: {
            plugin.CTR_ACT_PROCESSED: 0,
            plugin.CTR_ACT_ERRORED: 0,
        },
        plugin.CTR_SRC_DATA: {
            plugin.CTR_ACT_UPDATE_COLUMNS: 0,
            plugin.CTR_ACT_UPDATE_ROWS: 0,
            plugin.CTR_ACT_DELTA_COLUMNS: 0,
            plugin.CTR_ACT_DELTA_ROWS: 0,
            plugin.CTR_ACT_ERRORED: 0,
        },
        plugin.CTR_SRC_EGRESS: {
            plugin.CTR_ACT_QUEUE_COLUMNS: 0,
            plugin.CTR_ACT_QUEUE_ROWS: 0,
            plugin.CTR_ACT_SHEET_COLUMNS: 0,
            plugin.CTR_ACT_SHEET_ROWS: 0,
            plugin.CTR_ACT_DATABASE_COLUMNS: 0,
            plugin.CTR_ACT_DATABASE_ROWS: 0,
            plugin.CTR_ACT_ERRORED: 0,
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
            plugin.CTR_ACT_ERRORED: 0,
        },
        plugin.CTR_SRC_FILES: {
            plugin.CTR_ACT_ERRORED: 0,
        },
        plugin.CTR_SRC_DATA: {
            plugin.CTR_ACT_PREVIOUS_ROWS: 0,
            plugin.CTR_ACT_ERRORED: 0,
        },
        plugin.CTR_SRC_EGRESS: {
            plugin.CTR_ACT_ERRORED: 0,
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
    plugin.config.force_reprocessing = False
    plugin.config.force_downloads = False
    plugin.config.disable_repo_uploads = True
    plugin.config.disable_repo_downloads = True
    plugin.config.disable_source_downloads = False
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
        super().__init__(name, plugin.Repos(
            preview={"drive_folder": "PLACEHOLDER"},
            release={"drive_folder": drive_folder},
        ))


if __name__ == "__main__":
    sys.exit(pytest.main(["-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache", __file__, ]))
