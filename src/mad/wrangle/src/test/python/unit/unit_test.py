import copy
import importlib
import os
import re
import shutil
import sys
import unittest
from os.path import *

import polars as pl
import pytest

sys.path.append('../../../main/python')

from wrangle import plugin
from wrangle.plugin import Plugin, DownloadResult, DownloadStatus
from wrangle.plugin.logger import dataframe_print

########################################################################################################################
# NOTES:
#   - Include in test runner templates for realtime, unbuffered output: PYTHONUNBUFFERED=1;JB_DISABLE_BUFFERING=1
########################################################################################################################


DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))


# noinspection PyMethodMayBeStatic
class WrangleTest(unittest.TestCase):

    def test_balances_local_blank(self):
        self.run_plugin("balances", {"blank": merge_asserts(ASSERT_NOOP, {
        })}, verifications={
            "__Balances_Current.csv": [
                verify_does_not_exist(),
            ],
        }, disable_downloads=True, disable_uploads=True, repo_scope=plugin.RepoScope.LOCAL, log_level="info")

    def test_currency_local_blank(self):
        self.run_plugin("currency", {"blank": merge_asserts(ASSERT_NOOP, {
        })}, verifications={
            "__Currency__Current.csv": [
                verify_does_not_exist(),
            ],
        }, disable_downloads=True, disable_uploads=True, repo_scope=plugin.RepoScope.LOCAL, log_level="info")

    def test_currency_release_current(self):
        self.run_plugin("currency", {"current": merge_asserts(ASSERT_RUN, {
            "counter_equals": {
                plugin.CTR_SRC_DATA: {
                    plugin.CTR_ACT_PREVIOUS_COLUMNS: 15,
                    plugin.CTR_ACT_CURRENT_COLUMNS: 15,
                    plugin.CTR_ACT_UPDATE_COLUMNS: 15,
                    plugin.CTR_ACT_DELTA_COLUMNS: 15,
                },
            },
            "counter_greater": {
                plugin.CTR_SRC_DATA: {
                    plugin.CTR_ACT_DELTA_ROWS: 1,
                },
            },
        })}, verifications={
            "__Currency_Current.csv": [
                verify_size(),
                verify_contiguous_dates(),
                verify_nones_per_row(),
                verify_zeroes_per_col(exclude=".*Delta.*")
            ],
            "_Sheet_Rates_Currency.csv": [
                verify_size(),
                verify_contiguous_dates(),
                verify_nones_per_row(),
                verify_max_zeroes_per_row()
            ],
            "_Database_Currency.csv": [
                verify_size(),
                verify_contiguous_dates(),
                verify_nones_per_row(),
                verify_zeroes_per_col(exclude=".*type=delta.*")
            ],
        }, disable_downloads=False, disable_uploads=True, repo_scope=plugin.RepoScope.RELEASE, log_level="info")

    @pytest.mark.skip(reason="requires update")
    def test_equity_release_current(self):
        self.run_plugin("equity", {"current": merge_asserts(ASSERT_RUN, {
            "counter_greater": {
                plugin.CTR_SRC_DATA: {
                    plugin.CTR_ACT_PREVIOUS_COLUMNS: 200,
                    plugin.CTR_ACT_CURRENT_COLUMNS: 144,
                    plugin.CTR_ACT_UPDATE_COLUMNS: 108,
                    plugin.CTR_ACT_DELTA_COLUMNS: 144,
                },
            },
        })}, disable_downloads=False, disable_uploads=True, repo_scope=plugin.RepoScope.RELEASE, log_level="info")

    @pytest.mark.skip(reason="requires update")
    def test_interest_release_current(self):
        self.run_plugin("interest", {"current": merge_asserts(ASSERT_RUN, {
            "counter_equals": {
                plugin.CTR_SRC_DATA: {
                    plugin.CTR_ACT_PREVIOUS_COLUMNS: 18,
                    plugin.CTR_ACT_CURRENT_COLUMNS: 18,
                    plugin.CTR_ACT_UPDATE_COLUMNS: 18,
                    plugin.CTR_ACT_DELTA_COLUMNS: 18,
                },
            },
        })}, disable_downloads=False, disable_uploads=True, repo_scope=plugin.RepoScope.RELEASE, log_level="info", verifications={
            "__Interest_Current.csv": [verify_size(), verify_nones_per_row(), verify_contiguous_dates()],
            "_Sheet_Rates_Interest.csv": [verify_size(), verify_nones_per_row(), verify_contiguous_dates(), verify_max_zeroes_per_row(0)],
            "_Database_Interest.csv": [verify_size(), verify_nones_per_row(), verify_contiguous_dates()],
        })

    @pytest.mark.skip(reason="very slow")
    def test_library_sheet(self):
        test = Test("Test", "SOME_NON_EXISTANT_GUID")

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
        test = Test("Test", "SOME_NON_EXISTANT_GUID")
        reset_config()
        invalid_cache = "Invalid"
        invalid_path = abspath(f"{test.local_cache}/_Database_{invalid_cache}.csv")
        for result in [
            test.database_download(invalid_cache, "SELECT 1", force=True),
            test.database_download(invalid_cache, "SELECT 1", force=False),
            test.database_download(invalid_cache, "SELECT 1", check=False, force=True),
        ]:
            self.assertEqual(DownloadResult(DownloadStatus.FAILED, None), result)
        self.assertFalse(isfile(invalid_path))
        cache_cache = "Cache"
        cache_path = abspath(f"{test.local_cache}/_Database_{cache_cache}.csv")
        with open(cache_path, "w") as fh:
            fh.write("Date,Rate\n2020-01-01,1.0\n")
        self.assertEqual(DownloadResult(DownloadStatus.CACHED, cache_path), test.database_download(cache_cache, "SELECT 1"))
        plugin.config.disable_downloads = True
        self.assertEqual(DownloadResult(DownloadStatus.CACHED, cache_path), test.database_download(cache_cache, "SELECT 1"))

    def test_library_dataframe(self):
        test = Test("Test", "SOME_NON_EXISTANT_GUID")

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
        calls = [0]

        def counting(df):
            calls[0] += 1
            return df

        t.state_cache(self._df([("2020-03-01", 3.0)]), counting)
        self.assertEqual(2, calls[0])

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

    # TODO: Remove?
    # def test_state_cache_disable_downloads(self):
    #     t = self._setup_state_test("test-5")
    #     plugin.config.disable_downloads = True
    #     update = self._df([("2020-04-01", 4.0)])
    #     delta, current, _ = t.state_cache(update)
    #     self.assertEqual(0, len(delta))
    #     self.assertEqual(3, len(current))
    #
    # def test_state_cache_disable_downloads_aggregate_not_applied(self):
    #     t = self._setup_state_test("test-5")
    #     t.state_cache(self._df([("2020-01-01", 1.0), ("2020-02-01", 2.0), ("2020-03-01", 3.0)]),
    #                   lambda df: df.with_columns((pl.col("Value") * 2).alias("Double")))
    #     t.reset_counters()
    #     plugin.config.disable_downloads = True
    #     _, current, _ = t.state_cache(
    #         self._df([("2020-04-01", 4.0)]),
    #         lambda df: df.with_columns((pl.col("Value") * 100).alias("Double"))
    #     )
    #     self.assertIn("Double", current.columns)
    #     self.assertEqual([2.0, 4.0, 6.0], current.sort("Date")["Double"].to_list())
    #     dates = [str(d) for d in current["Date"].to_list()]
    #     self.assertNotIn("2020-04-01", dates)
    #
    # def test_state_cache_disable_downloads_returns_current_as_previous(self):
    #     t = self._setup_state_test("test-5")
    #     plugin.config.disable_downloads = True
    #     update = self._df([("2020-04-01", 4.0)])
    #     delta, current, previous = t.state_cache(update)
    #     self.assertEqual(0, len(delta))
    #     self.assertEqual(len(current), len(previous))
    #     self.assertEqual(current["Date"].to_list(), previous["Date"].to_list())
    #     self.assertEqual(current["Value"].to_list(), previous["Value"].to_list())
    #
    # def test_state_cache_multi_key_disable_downloads(self):
    #     t = self._setup_state_test("mk-11")
    #     t.state_cache(self._mk_df([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]),
    #                   key_columns=["Date", "Account ID"])
    #     t.reset_counters()
    #     plugin.config.disable_downloads = True
    #     delta, current, _ = t.state_cache(
    #         self._mk_df([("2026-01-01", "acc-1", 999.0)]),
    #         key_columns=["Date", "Account ID"])
    #     self.assertEqual(0, len(delta))
    #     self.assertEqual(2, len(current))

    def _price_df(self, date_price_pairs, ticker="AAPL"):
        return pl.DataFrame({
            "Date": [p[0] for p in date_price_pairs],
            f"{ticker} Price Close": [float(p[1]) for p in date_price_pairs],
        }).with_columns(pl.col("Date").str.to_date())

    def _price_change_agg(self, ticker="AAPL"):
        price_col = f"{ticker} Price Close"
        change_col = f"{ticker} Price Close 1d-Change Percentage"

        def _agg(df):
            str_cols = [c for c, t in zip(df.columns, df.dtypes)
                        if str(t) in ('String', 'Utf8', 'Null') and c != 'Date']
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
            str_cols = [_c for _c, _t in zip(df.columns, df.dtypes)
                        if str(_t) in ('String', 'Utf8', 'Null') and _c != 'Date']
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
        self.assertTrue(isfile(join(t.local_cache, "__Test_Current.csv")))
        self.assertTrue(isfile(join(t.local_cache, "__Test_Update.csv")))
        self.assertTrue(isfile(join(t.local_cache, "__Test_Delta.csv")))
        self.assertFalse(isfile(join(t.local_cache, "__Test_Previous.csv")))
        t.reset_counters()
        t.state_cache(self._price_df([
            ("2020-01-01", 100.0), ("2020-02-01", 200.0),
            ("2020-03-01", 300.0), ("2020-04-01", 400.0),
        ]), self._price_change_agg())
        self.assertTrue(isfile(join(t.local_cache, "__Test_Previous.csv")))
        self.assertEqual(4, len(t.csv_read(join(t.local_cache, "__Test_Current.csv"))))
        self.assertEqual(2, len(t.csv_read(join(t.local_cache, "__Test_Previous.csv"))))
        self.assertEqual(4, len(t.csv_read(join(t.local_cache, "__Test_Update.csv"))))
        self.assertEqual(2, len(t.csv_read(join(t.local_cache, "__Test_Delta.csv"))))

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
            str_cols = [_c for _c, _t in zip(df.columns, df.dtypes)
                        if str(_t) in ('String', 'Utf8', 'Null') and _c != 'Date']
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
            str_cols = [_c for _c, _t in zip(df.columns, df.dtypes)
                        if str(_t) in ('String', 'Utf8', 'Null') and _c != 'Date']
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

    def _mk_df(self, rows):
        return pl.DataFrame({
            "Date": [r[0] for r in rows],
            "Account ID": [r[1] for r in rows],
            "Balance": [float(r[2]) for r in rows],
        }).with_columns(pl.col("Date").str.to_date())

    def test_state_cache_multi_key_first_run(self):
        t = self._setup_state_test("mk-1")
        delta, current, previous = t.state_cache(
            self._mk_df([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]),
            key_columns=["Date", "Account ID"])
        self.assertEqual(2, len(delta))
        self.assertEqual(2, len(current))
        self.assertEqual(0, len(previous))

    def test_state_cache_multi_key_no_change(self):
        t = self._setup_state_test("mk-2")
        data = self._mk_df([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)])
        t.state_cache(data, key_columns=["Date", "Account ID"])
        t.reset_counters()
        delta, current, _ = t.state_cache(data, key_columns=["Date", "Account ID"])
        self.assertEqual(0, len(delta))
        self.assertEqual(2, len(current))

    def test_state_cache_multi_key_value_change(self):
        t = self._setup_state_test("mk-3")
        t.state_cache(self._mk_df([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]),
                      key_columns=["Date", "Account ID"])
        t.reset_counters()
        delta, current, _ = t.state_cache(
            self._mk_df([("2026-01-01", "acc-1", 150.0), ("2026-01-01", "acc-2", 200.0)]),
            key_columns=["Date", "Account ID"])
        self.assertEqual(1, len(delta))
        self.assertEqual(150.0, delta.filter(pl.col("Account ID") == "acc-1")["Balance"][0])
        self.assertEqual(2, len(current))

    def test_state_cache_multi_key_new_account(self):
        t = self._setup_state_test("mk-4")
        t.state_cache(self._mk_df([("2026-01-01", "acc-1", 100.0)]),
                      key_columns=["Date", "Account ID"])
        t.reset_counters()
        delta, current, _ = t.state_cache(
            self._mk_df([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]),
            key_columns=["Date", "Account ID"])
        self.assertEqual(1, len(delta))
        self.assertEqual("acc-2", delta["Account ID"][0])
        self.assertEqual(2, len(current))

    def test_state_cache_multi_key_new_date(self):
        t = self._setup_state_test("mk-5")
        t.state_cache(self._mk_df([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]),
                      key_columns=["Date", "Account ID"])
        t.reset_counters()
        delta, current, _ = t.state_cache(
            self._mk_df([("2026-01-02", "acc-1", 110.0), ("2026-01-02", "acc-2", 210.0)]),
            key_columns=["Date", "Account ID"])
        self.assertEqual(2, len(delta))
        self.assertEqual(4, len(current))
        self.assertTrue(all(str(d) == "2026-01-02" for d in delta["Date"].to_list()))

    def test_state_cache_multi_key_partial_update(self):
        t = self._setup_state_test("mk-6")
        t.state_cache(self._mk_df([
            ("2026-01-01", "acc-1", 100.0),
            ("2026-01-01", "acc-2", 200.0),
        ]), key_columns=["Date", "Account ID"])
        t.reset_counters()
        delta, current, _ = t.state_cache(self._mk_df([
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
        delta, current, _ = t.state_cache(self._mk_df([
            ("2026-01-01", "acc-1", 100.0),
            ("2026-01-01", "acc-1", 999.0),
        ]), key_columns=["Date", "Account ID"])
        self.assertEqual(1, len(current))
        self.assertEqual(999.0, current["Balance"][0])
        self.assertEqual(1, len(delta))

    def test_state_cache_multi_key_update_supersedes_current(self):
        t = self._setup_state_test("mk-8")
        t.state_cache(self._mk_df([("2026-01-01", "acc-1", 100.0)]),
                      key_columns=["Date", "Account ID"])
        t.reset_counters()
        delta, current, previous = t.state_cache(
            self._mk_df([("2026-01-01", "acc-1", 999.0)]),
            key_columns=["Date", "Account ID"])
        self.assertEqual(1, len(delta))
        self.assertEqual(999.0, current["Balance"][0])
        self.assertEqual(100.0, previous["Balance"][0])

    def test_state_cache_multi_key_counters(self):
        t = self._setup_state_test("mk-9")
        t.state_cache(self._mk_df([("2026-01-01", "acc-1", 100.0)]),
                      key_columns=["Date", "Account ID"])
        self.assertEqual(1, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_UPDATE_COLUMNS))
        self.assertEqual(1, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_CURRENT_COLUMNS))
        self.assertEqual(1, t.get_counter(plugin.CTR_SRC_DATA, plugin.CTR_ACT_DELTA_COLUMNS))

    def test_state_cache_multi_key_clean(self):
        t = self._setup_state_test("mk-10")
        t.state_cache(self._mk_df([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]),
                      key_columns=["Date", "Account ID"])
        t.reset_counters()
        plugin.config.force_reprocessing = True
        delta, current, previous = t.state_cache(
            self._mk_df([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]),
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
            self._mk_df([("2026-01-01", "acc-1", 50.0), ("2026-01-01", "acc-2", 100.0)]),
            aggregate_function=_agg, key_columns=["Date", "Account ID"])
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

    def _setup_state_test(self, fixture):
        t = Test("Test", "SOME_NON_EXISTANT_GUID")
        t.local_cache = abspath(join(DIR_ROOT, "target", "data", f"state-{fixture}"))
        shutil.rmtree(t.local_cache, ignore_errors=True)
        os.makedirs(t.local_cache)
        src = join(DIR_ROOT, "src/test/resources/state", fixture)
        if isdir(src):
            for fname in os.listdir(src):
                shutil.copy(join(src, fname), join(t.local_cache, fname))
        plugin.config.force_reprocessing = False
        plugin.config.disable_downloads = False
        return t

    def _df(self, date_value_pairs):
        return pl.DataFrame({
            "Date": [p[0] for p in date_value_pairs],
            "Value": [float(p[1]) for p in date_value_pairs],
        }).with_columns(pl.col("Date").str.to_date())

    def run_plugin(self, name, tests_asserts, log_level="info",
                   prepare_only=False, enable_rerun=True, force_reprocessing=False, force_downloads=False,
                   disable_uploads=True, disable_downloads=False, repo_scope=plugin.RepoScope.LOCAL,
                   verifications=None):
        if verifications is None:
            verifications = {}
        if not disable_uploads and repo_scope == plugin.RepoScope.RELEASE:
            raise ValueError("Cannot enable uploads when repo_scope is RELEASE")
        plugin.config.log_level = log_level
        plugin.config.repo_scope = repo_scope
        plugin.config.force_reprocessing = force_reprocessing
        plugin.config.force_downloads = force_downloads
        plugin.config.disable_uploads = disable_uploads
        plugin.config.disable_downloads = disable_downloads
        plugin.database_close()
        dir_target = join(DIR_ROOT, "target")
        if not isdir(dir_target):
            os.makedirs(dir_target)
        plugin_name = getattr(importlib.import_module(f"wrangle.plugin.{name}"), name.title())()
        print("")
        for test in tests_asserts:
            self._load_caches(plugin_name, join(DIR_ROOT, "src/test/resources/repos", repo_scope, name, test))
            if not prepare_only:
                print(f"STARTING (run)     [{name.title()}]   [{test}]")
                plugin_name.run()
                print(f"FINISHED (run)     [{name.title()}]   [{test}]\n")
                self._assert_counters(plugin_name.get_counters(), tests_asserts[test])
                self._verify_outputs(plugin_name, verifications)
                if enable_rerun:
                    plugin_name.reset_counters()
                    print(f"STARTING (no-op)   [{name.title()}]   [{test}]")
                    plugin_name.run()
                    print(f"FINISHED (no-op)   [{name.title()}]   [{test}]\n\n")
                    self._assert_counters(plugin_name.get_counters(), ASSERT_NOOP)
                    self._verify_outputs(plugin_name, verifications)
                    plugin_name.reset_counters()
                    print(f"STARTING (reload)   [{name.title()}]   [{test}]")
                    plugin.config.force_reprocessing = True
                    plugin_name.run()
                    plugin.config.force_reprocessing = force_reprocessing
                    print(f"FINISHED (reload)   [{name.title()}]   [{test}]\n\n")
                    self._assert_counters(plugin_name.get_counters(), ASSERT_RELOAD)
                    self._verify_outputs(plugin_name, verifications)

    def _load_caches(self, plugin_name, source):
        if not isdir(source):
            raise FileNotFoundError(f"Test data directory [{source}] does not exist")
        shutil.rmtree(plugin_name.local_cache, ignore_errors=True)
        shutil.copytree(source, plugin_name.local_cache, ignore=shutil.ignore_patterns(".git*"))
        plugin_name.print_log(f"Files written from [{source}] to [{plugin_name.local_cache}]")

    def _verify_outputs(self, plugin_name, verifications):
        for filename, funcs in verifications.items():
            file_path = join(plugin_name.local_cache, filename)
            for func in funcs:
                if not func(file_path):
                    self.fail(f"Verification [{func.__name__}] failed for [{filename}]")

    def _assert_counters(self, actual, asserts):
        comparators = [
            ("counter_equals", self.assertEqual, "equals", "!="),
            ("counter_less", self.assertLessEqual, "less than", ">="),
            ("counter_greater", self.assertGreaterEqual, "greater than", "<="),
        ]
        for comparator_key, assert_fn, label, op in comparators:
            if comparator_key not in asserts:
                continue
            for counter_source, actions in asserts[comparator_key].items():
                for counter_action, expected in actions.items():
                    actual_value = actual.get(counter_source, {}).get(counter_action, 0)
                    assert_fn(actual_value, expected,
                              f"Counter [{counter_source} {counter_action}] {label} assertion failed [{actual_value}] {op} [{expected}]")

    def setUp(self):
        print("")
        shutil.rmtree(join(DIR_ROOT, "target", "data"), ignore_errors=True)
        os.makedirs(join(DIR_ROOT, "target", "data"))
        shutil.rmtree(join(DIR_ROOT, "target", "runtime-unit"), ignore_errors=True)
        os.makedirs(join(DIR_ROOT, "target", "runtime-unit"))
        reset_config(log="info")

    def tearDown(self):
        reset_config()


def _leading_zero_rows(csv_df, numeric_cols):
    count = 0
    for i in range(len(csv_df)):
        row = csv_df.row(i, named=True)
        if any(row[col] == 0 for col in numeric_cols if row[col] is not None):
            count = i + 1
        else:
            break
    return count


def _load_csv(file_path):
    return pl.read_csv(file_path, try_parse_dates=True)


def _filter_cols(csv_df, include=None, exclude=None):
    cols = csv_df.columns
    if include is not None:
        cols = [c for c in cols if re.search(include, c)]
    if exclude is not None:
        cols = [c for c in cols if not re.search(exclude, c)]
    return cols


def verify_does_not_exist():
    def _verify(file_path):
        if isfile(file_path):
            dataframe_print("Verify", pl.DataFrame(), f"verify_does_not_exist: [{file_path}] exists", level="error")
            return False
        return True

    _verify.__name__ = "verify_does_not_exist"
    return _verify


def verify_size(min_rows=1, max_rows=None):
    def _verify(file_path):
        csv_df = _load_csv(file_path)
        count = len(csv_df)
        if count < min_rows:
            dataframe_print("Verify", csv_df, f"{label}: expected >={min_rows} rows, got {count}", level="error")
            return False
        if max_rows is not None and count > max_rows:
            dataframe_print("Verify", csv_df, f"{label}: expected <={max_rows} rows, got {count}", level="error")
            return False
        return True

    label = f"verify_size_{min_rows}_{max_rows}_rows"
    _verify.__name__ = label
    return _verify


def verify_nones_per_row(max_nones=0, include=None, exclude=None):
    def _verify(file_path):
        csv_df = _load_csv(file_path)
        cols = _filter_cols(csv_df, include, exclude)
        if not cols:
            return True
        fail_rows = csv_df.filter(pl.sum_horizontal(pl.col(c).is_null().cast(pl.Int32) for c in cols) > max_nones)
        if not fail_rows.is_empty():
            dataframe_print("Verify", fail_rows, f"{label}: rows with >{max_nones} nones", level="error")
            return False
        return True

    label = f"verify_max_{max_nones}_nones_per_row"
    _verify.__name__ = label
    return _verify


def verify_max_nones_per_col(max_nones=0, include=None, exclude=None):
    def _verify(file_path):
        csv_df = _load_csv(file_path)
        cols = _filter_cols(csv_df, include, exclude)
        failed = [c for c in cols if csv_df[c].null_count() > max_nones]
        if failed:
            dataframe_print("Verify", csv_df.select(failed), f"{label}: columns with >{max_nones} nones: {failed}", level="error")
            return False
        return True

    label = f"verify_max_{max_nones}_nones_per_col"
    _verify.__name__ = label
    return _verify


def verify_max_zeroes_per_row(max_zeroes=0, after_first_rows=False, include=None, exclude=None):
    def _verify(file_path):
        csv_df = _load_csv(file_path)
        numeric_cols = [col for col in _filter_cols(csv_df, include, exclude) if
                        csv_df[col].dtype in (pl.Float32, pl.Float64, pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64)]
        if not numeric_cols:
            return True
        data_df = csv_df.slice(_leading_zero_rows(csv_df, numeric_cols)) if after_first_rows else csv_df
        zero_count = pl.sum_horizontal((pl.col(c) == 0).cast(pl.Int32) for c in numeric_cols)
        fail_rows = data_df.filter(zero_count > max_zeroes)
        if not fail_rows.is_empty():
            dataframe_print("Verify", fail_rows, f"{label}: rows with >{max_zeroes} zeros", level="error")
            return False
        return True

    label = f"verify_max_{max_zeroes}_zeroes_per_row" + ("_after_first_rows" if after_first_rows else "")
    _verify.__name__ = label
    return _verify


def verify_zeroes_per_col(max_zeroes=0, include=None, exclude=None):
    def _verify(file_path):
        csv_df = _load_csv(file_path)
        numeric_cols = [col for col in _filter_cols(csv_df, include, exclude) if
                        csv_df[col].dtype in (pl.Float32, pl.Float64, pl.Int8, pl.Int16, pl.Int32, pl.Int64, pl.UInt8, pl.UInt16, pl.UInt32, pl.UInt64)]
        failed = [c for c in numeric_cols if (csv_df[c] == 0).sum() > max_zeroes]
        if failed:
            dataframe_print("Verify", csv_df.select(failed), f"{label}: columns with >{max_zeroes} zeros: {failed}", level="error")
            return False
        return True

    label = f"verify_max_{max_zeroes}_zeroes_per_col"
    _verify.__name__ = label
    return _verify


def verify_contiguous_dates(start_date=None, end_date=None, max_gap_days=1):
    def _verify(file_path):
        csv_df = _load_csv(file_path)
        if "Date" not in csv_df.columns:
            dataframe_print("Verify", csv_df, "verify_contiguous_dates: no Date column", level="error")
            return False
        dates = csv_df.sort("Date")["Date"].drop_nulls().to_list()
        if len(dates) < 2:
            return True
        if start_date is not None and dates[0] != start_date:
            dataframe_print("Verify", csv_df.head(1), f"verify_contiguous_dates: expected start {start_date}, got {dates[0]}", level="error")
            return False
        if end_date is not None and dates[-1] != end_date:
            dataframe_print("Verify", csv_df.tail(1), f"verify_contiguous_dates: expected end {end_date}, got {dates[-1]}", level="error")
            return False
        diffs = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        if max_gap_days is not None:
            for i, diff in enumerate(diffs):
                if diff > max_gap_days:
                    gap_df = csv_df.filter(pl.col("Date").is_in([dates[i], dates[i + 1]]))
                    dataframe_print("Verify", gap_df, f"verify_contiguous_dates: gap of {diff} days between {dates[i]} and {dates[i + 1]} exceeds max {max_gap_days}", level="error")
                    return False
        else:
            min_diff, max_diff = min(diffs), max(diffs)
            if 28 <= min_diff and max_diff <= 31:
                for i in range(len(dates) - 1):
                    if dates[i + 1].year * 12 + dates[i + 1].month - (dates[i].year * 12 + dates[i].month) != 1:
                        gap_df = csv_df.filter(pl.col("Date").is_in([dates[i], dates[i + 1]]))
                        dataframe_print("Verify", gap_df, f"verify_contiguous_dates: gap between {dates[i]} and {dates[i + 1]}", level="error")
                        return False
        return True

    _verify.__name__ = "verify_contiguous_dates"
    return _verify


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
    "counter_greater": {
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
            plugin.CTR_ACT_PERSISTED: 0,
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
    "counter_greater": {
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
    "counter_greater": {
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
    plugin.config.disable_uploads = True
    plugin.config.disable_downloads = False
    plugin.database_close()


class Test(Plugin):
    def _run(self):
        pass

    def __init__(self, name, drive_folder):
        super().__init__(name, plugin.Repos(
            preview={"drive_folder": "PLACEHOLDER"},
            release={"drive_folder": drive_folder},
        ))


if __name__ == "__main__":
    sys.exit(pytest.main(["-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache", __file__, ]))
