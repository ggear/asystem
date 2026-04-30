import copy
import importlib
import os
import shutil
import sys
import unittest
from os.path import *

import polars as pl
import pytest
from unittest.mock import patch, MagicMock

########################################################################################################################
# NOTES:
#   - Include in test runner templates for realtime, unbuffered output: PYTHONUNBUFFERED=1;JB_DISABLE_BUFFERING=1
########################################################################################################################

sys.path.append('../../../main/python')

from wrangle.plugin import library
from wrangle.plugin.library import Library, DownloadResult, DownloadStatus

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

for key, value in list(library.load_profile(join(DIR_ROOT, ".env")).items()):
    os.environ[key] = value


def reset_config(log="warning"):
    library.config.log_level = log
    library.config.clean = False
    library.config.disable_uploads = True
    library.config.disable_downloads = False
    library.database = None


class WrangleTest(unittest.TestCase):

    def test_adhoc(self):
        self.run_module("interest", {"success_typical": ASSERT_RUN},
                        clean=False,
                        disable_downloads=False,
                        disable_uploads=True,
                        enable_rerun=False,
                        log="info",
                        )

    def test_currency_typical(self):
        self.run_module("currency", {"success_typical": merge_asserts(ASSERT_RUN, {
            "counter_equals": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_PREVIOUS_COLUMNS: 15,
                    library.CTR_ACT_CURRENT_COLUMNS: 15,
                    library.CTR_ACT_UPDATE_COLUMNS: 15,
                    library.CTR_ACT_DELTA_COLUMNS: 15,
                },
            },
        })})

    def test_currency_partial(self):
        self.run_module("currency", {"success_partial": merge_asserts(ASSERT_RUN, {
            "counter_equals": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_PREVIOUS_COLUMNS: 15,
                    library.CTR_ACT_CURRENT_COLUMNS: 15,
                    library.CTR_ACT_UPDATE_COLUMNS: 15,
                    library.CTR_ACT_DELTA_COLUMNS: 15,
                },
            },
        })})

    def test_equity_typical(self):
        self.run_module("equity", {"success_typical": merge_asserts(ASSERT_RUN, {
            "counter_greater": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_PREVIOUS_COLUMNS: 200,
                    library.CTR_ACT_CURRENT_COLUMNS: 144,
                    library.CTR_ACT_UPDATE_COLUMNS: 108,
                    library.CTR_ACT_DELTA_COLUMNS: 144,
                },
            },
        })})

    def test_equity_partial(self):
        self.run_module("equity", {"success_partial": merge_asserts(ASSERT_RUN, {
            "counter_greater": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_PREVIOUS_COLUMNS: 200,
                    library.CTR_ACT_CURRENT_COLUMNS: 144,
                    library.CTR_ACT_UPDATE_COLUMNS: 126,
                    library.CTR_ACT_DELTA_COLUMNS: 144,
                },
            },
        })})

    def test_interest_typical(self):
        self.run_module("interest", {"success_typical": merge_asserts(ASSERT_RUN, {
            "counter_equals": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_PREVIOUS_COLUMNS: 18,
                    library.CTR_ACT_CURRENT_COLUMNS: 18,
                    library.CTR_ACT_UPDATE_COLUMNS: 18,
                    library.CTR_ACT_DELTA_COLUMNS: 18,
                },
            },
        })})

    def test_interest_partial(self):
        self.run_module("interest", {"success_partial": merge_asserts(ASSERT_RUN, {
            "counter_equals": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_PREVIOUS_COLUMNS: 18,
                    library.CTR_ACT_CURRENT_COLUMNS: 18,
                    library.CTR_ACT_UPDATE_COLUMNS: 18,
                    library.CTR_ACT_DELTA_COLUMNS: 18,
                },
            },
        })})

    def test_balances_typical(self):
        self.run_module("balances", {"success_typical": merge_asserts(ASSERT_RUN, {
            # "counter_equals": {
            #     library.CTR_SRC_FILES: {
            #         library.CTR_ACT_PROCESSED: 0,
            #     },
            # },
            # "counter_greater": {
            #     library.CTR_SRC_DATA: {
            #         library.CTR_ACT_DELTA_COLUMNS: 1,
            #         library.CTR_ACT_CURRENT_COLUMNS: 1,
            #         library.CTR_ACT_UPDATE_COLUMNS: 1,
            #     },
            # },
        })})

    def test_library_sheet(self):
        test = Test("Test", "SOME_NON_EXISTANT_GUID")

        def _sheet_read(result, schema={}):
            if result.status == DownloadStatus.FAILED:
                return test.dataframe_new()
            return test.csv_read(result.file_path, schema=schema)

        missing_name = "missing"
        missing_key = "!"
        missing_str = "[]"
        library.config.log_level = "fatal"
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
        library.config.log_level = "fatal"
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
        library.config.log_level = "info"
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
        test_str_utf = ["str" for _ in range(0, len(test_type_number))]
        test_str_numeric = [test.dataframe_type_to_str(dtype) for dtype in test_type_number.values()]
        library.config.log_level = "info"
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
        data_str = "[Exchange Symbol(str), Holdings Quantity({}), Unit Price(f64), Watch Value(f64), Watch Quantity(i64), Baseline Quantity(f64)]"
        data_str_type = [test.dataframe_type_to_str(data_type[column]) for column in data_type]
        for result in [
            test.sheet_download(data_key, data_name + "-1", "Indexes", 2, write_cache=True),
            test.sheet_download(data_key, data_name + "-1", "Indexes", 2, write_cache=False),
            test.sheet_download(data_key, data_name + "-1", "Indexes", 2, write_cache=True),
            test.sheet_download(data_key, data_name + "-1", "Indexes", 2, read_cache=False, write_cache=True),
        ]:
            data_df = _sheet_read(result)
            self.assertEqual(data_str.format("f64"), test.dataframe_to_str(data_df))
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
        """With library.database=None and no cache file, database_download returns
        (False, False) and never writes a file; with a cache file, it returns (True, False)."""
        test = Test("Test", "SOME_NON_EXISTANT_GUID")
        reset_config()
        invalid_cache = "Invalid"
        invalid_path = abspath("{}/_{}_Database_Download.csv".format(test.input, invalid_cache))
        for result in [
            test.database_download(invalid_cache, "SELECT 1", force=True),
            test.database_download(invalid_cache, "SELECT 1", force=False),
            test.database_download(invalid_cache, "SELECT 1", check=False, force=True),
        ]:
            self.assertEqual(DownloadResult(DownloadStatus.FAILED, None), result)
        self.assertFalse(isfile(invalid_path))
        cache_cache = "Cache"
        cache_path = abspath("{}/_{}_Database_Download.csv".format(test.input, cache_cache))
        with open(cache_path, "w") as fh:
            fh.write("Date,Rate\n2020-01-01,1.0\n")
        self.assertEqual(DownloadResult(DownloadStatus.CACHED, cache_path), test.database_download(cache_cache, "SELECT 1"))
        library.config.disable_downloads = True
        self.assertEqual(DownloadResult(DownloadStatus.CACHED, cache_path), test.database_download(cache_cache, "SELECT 1"))

    def test_library_dataframe(self):
        test = Test("Test", "SOME_NON_EXISTANT_GUID")

        df_empty_str = "[{}]"
        df_empty_type = {"C1": pl.Int16}
        self.assertEqual(df_empty_str.format(""), test.dataframe_to_str(test.dataframe_new()))
        self.assertEqual(df_empty_str.format(""), test.dataframe_to_str(test.dataframe_new([])))
        self.assertEqual(df_empty_str.format(""), test.dataframe_to_str(test.dataframe_new([], {})))
        self.assertEqual(df_empty_str.format("C1(i16)"), test.dataframe_to_str(test.dataframe_new([], df_empty_type)))

        df_data_str = "[C1({}), C2({}), C3({})]"
        df_data_type = {"C1": pl.Int64, "C2": pl.Utf8, "C3": pl.Utf8}
        df_data = [{"C1": 1, "C2": 1.1, "C3": "1"}, {"C1": 2, "C2": 2.2, "C3": "2"},
                   {"C1": None, "C2": None, "C3": None}]
        self.assertEqual(df_data_str.format("i64", "f64", "str"),
                         test.dataframe_to_str(test.dataframe_new(df_data)))
        self.assertEqual(df_data_str.format("i64", "f64", "str"),
                         test.dataframe_to_str(test.dataframe_new(df_data, {})))
        self.assertEqual(df_data_str.format("i64", "str", "str"),
                         test.dataframe_to_str(test.dataframe_new(df_data, df_data_type)))
        self.assertEqual(3,
                         len((test.dataframe_new(df_data, schema={column: pl.Utf8 for column in df_data[0]}))))

        df_lots_cols = 50
        df_lots_rows = 100
        df_lots = [{"C{}".format(c): v * v / 0.2 for c in range(1, df_lots_cols + 1)} for v in
                   range(1, df_lots_rows + 1)]
        self.assertEqual(True, isinstance(test.dataframe_to_str(test.dataframe_new(df_lots, print_label="lots")), str))
        self.assertEqual(True,
                         isinstance(test.dataframe_to_str(test.dataframe_new(schema=df_data_type, print_label="lots")),
                                    str))
        self.assertEqual(False,
                         isinstance(test.dataframe_to_str(test.dataframe_new(df_lots, print_label="lots")), list))
        self.assertEqual(True, isinstance(test.dataframe_to_str(test.dataframe_new(df_lots, print_label="lots"), False),
                                          list))
        self.assertEqual(df_lots_rows + 6,
                         len(test.dataframe_to_str(test.dataframe_new(df_lots, print_label="lots"), False, -1)))
        self.assertEqual(df_lots_rows + 6,
                         len(test.dataframe_to_str(test.dataframe_new(df_lots, print_label="lots"), False, 100)))
        self.assertEqual(5 + 7, len(test.dataframe_to_str(test.dataframe_new(df_lots, print_label="lots"), False, 5)))
        self.assertEqual(0 + 7, len(test.dataframe_to_str(test.dataframe_new(df_lots, print_label="lots"), False, 0)))
        self.assertEqual(df_lots_rows, len((test.dataframe_new(df_lots))))
        self.assertEqual(df_lots_rows, len((test.dataframe_new(df_lots, schema={"SOME UNKNOWN COLUMN": pl.Utf8}))))
        self.assertEqual(df_lots_rows,
                         len((test.dataframe_new(df_lots, schema={column: pl.Utf8 for column in df_data[0]}))))
        self.assertEqual(df_lots_rows,
                         len((test.dataframe_new(df_lots, schema={column: pl.Utf8 for column in df_lots[0]}))))

    def test_state_cache_first_run(self):
        """No pre-existing state: all update rows appear in delta and current; previous is empty."""
        t = self._setup_state_test("test-1")
        update = self._df([("2020-01-01", 1.0), ("2020-02-01", 2.0)])
        delta, current, previous = t.state_cache(update)
        self.assertEqual(2, len(delta))
        self.assertEqual(2, len(current))
        self.assertEqual(0, len(previous))

    def test_state_cache_append_rows(self):
        """New rows added to an existing cache: delta contains only the new row."""
        t = self._setup_state_test("test-2")
        update = self._df([("2020-01-01", 1.0), ("2020-02-01", 2.0), ("2020-03-01", 3.0)])
        delta, current, previous = t.state_cache(update)
        self.assertEqual(1, len(delta))
        self.assertEqual("2020-03-01", str(delta.sort("Date")["Date"][0]))
        self.assertEqual(3.0, delta.sort("Date")["Value"][0])
        self.assertEqual(3, len(current))
        self.assertEqual(2, len(previous))

    def test_state_cache_changed_values(self):
        """Changed row value: delta holds the current (new) value, not the previous value."""
        t = self._setup_state_test("test-3")
        update = self._df([("2020-01-01", 1.0), ("2020-02-01", 2.5)])
        delta, current, previous = t.state_cache(update)
        self.assertEqual(1, len(delta))
        self.assertEqual(2.5, delta["Value"][0])

    def test_state_cache_new_column(self):
        """Update adds a new column: current carries real values; delta rows carry current values."""
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
        """Empty update DataFrame: no delta produced, current and previous both reflect prior state."""
        t = self._setup_state_test("test-5")
        update = pl.DataFrame(schema={"Date": pl.Date, "Value": pl.Float64})
        delta, current, previous = t.state_cache(update)
        self.assertEqual(0, len(delta))
        self.assertEqual(3, len(current))
        self.assertEqual(3, len(previous))

    def test_state_cache_idempotent(self):
        """Re-running with identical data produces no delta on the second call."""
        t = self._setup_state_test("test-2")
        update = self._df([("2020-01-01", 1.0), ("2020-02-01", 2.0)])
        t.state_cache(update)
        t.reset_counters()
        delta, current, _ = t.state_cache(update)
        self.assertEqual(0, len(delta))
        self.assertEqual(2, len(current))

    def test_state_cache_with_aggregate(self):
        """Aggregate function is applied exactly once to the final merged dataset."""
        t = self._setup_state_test("test-1")
        update = self._df([("2020-01-01", 10.0), ("2020-02-01", 20.0), ("2020-03-01", 30.0)])
        delta, current, _ = t.state_cache(
            update,
            lambda df: df.with_columns((pl.col("Value") * 2).alias("Double"))
        )
        self.assertIn("Double", current.columns)
        self.assertEqual([20.0, 40.0, 60.0], current.sort("Date")["Double"].to_list())
        self.assertEqual(3, len(delta))

    def test_state_cache_disable_downloads(self):
        """config.disable_downloads=True skips all update processing; delta is empty."""
        t = self._setup_state_test("test-5")
        library.config.disable_downloads = True
        update = self._df([("2020-04-01", 4.0)])
        delta, current, _ = t.state_cache(update)
        self.assertEqual(0, len(delta))
        self.assertEqual(3, len(current))

    def test_state_cache_no_new_rows(self):
        """Update contains the same dates and values as the existing state: delta is empty."""
        t = self._setup_state_test("test-2")
        update = self._df([("2020-01-01", 1.0), ("2020-02-01", 2.0)])
        delta, current, previous = t.state_cache(update)
        self.assertEqual(0, len(delta))
        self.assertEqual(2, len(current))
        self.assertEqual(2, len(previous))

    def test_state_cache_subset_rows(self):
        """Update covers only a subset of existing dates with unchanged values: current keeps all rows and delta is empty."""
        t = self._setup_state_test("test-5")
        update = self._df([("2020-01-01", 1.0)])
        delta, current, _ = t.state_cache(update)
        self.assertEqual(0, len(delta))
        self.assertEqual(3, len(current))
        dates = [str(d) for d in current.sort("Date")["Date"].to_list()]
        self.assertEqual(["2020-01-01", "2020-02-01", "2020-03-01"], dates)

    def test_state_cache_deleted_column(self):
        """Update omits a column that existed in current: schema is preserved but values become null."""
        t = self._setup_state_test("test-6")
        update = self._df([("2020-01-01", 1.0), ("2020-02-01", 2.0)])
        delta, current, previous = t.state_cache(update)
        self.assertIn("Extra", current.columns)
        self.assertIsNone(current.sort("Date")["Extra"][0])
        self.assertEqual(10.0, previous.sort("Date")["Extra"][0])
        self.assertEqual(2, len(delta))
        self.assertIsNone(delta.sort("Date")["Extra"][0])

    def test_state_cache_force_reload(self):
        """config.clean=True deletes current before processing: full rebuild from update, previous becomes empty."""
        t = self._setup_state_test("test-2")
        library.config.clean = True
        update = self._df([("2020-01-01", 1.0), ("2020-02-01", 2.0), ("2020-03-01", 3.0)])
        delta, current, previous = t.state_cache(update)
        self.assertEqual(3, len(delta))
        self.assertEqual(3, len(current))
        self.assertEqual(0, len(previous))

    def test_state_cache_invalid_schema(self):
        """Update with wrong first column name or non-Date type raises SchemaError immediately."""
        t = self._setup_state_test("test-1")
        with self.assertRaises(pl.exceptions.SchemaError):
            t.state_cache(pl.DataFrame({"NotDate": ["x"], "Value": [1.0]}))
        with self.assertRaises(pl.exceptions.SchemaError):
            t.state_cache(pl.DataFrame({"Date": ["2020-01-01"], "Value": [1.0]}))

    def test_state_cache_orphaned_previous(self):
        """Previous CSV exists without a matching Current CSV: orphaned previous is deleted and run is treated as first."""
        t = self._setup_state_test("test-7")
        update = self._df([("2020-01-01", 1.0), ("2020-02-01", 2.0)])
        delta, current, previous = t.state_cache(update)
        self.assertEqual(2, len(delta))
        self.assertEqual(2, len(current))
        self.assertEqual(0, len(previous))

    def test_state_cache_duplicate_dates_in_update(self):
        """Duplicate dates in update: the last occurrence (by input order) wins."""
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
        """Update dates are entirely new: all update rows become delta; existing current rows are preserved."""
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
        """Update mixes unchanged, changed, and new rows: delta contains only changed+new."""
        t = self._setup_state_test("test-5")
        update = self._df([("2020-01-01", 1.0), ("2020-02-01", 2.5), ("2020-04-01", 4.0)])
        delta, current, _ = t.state_cache(update)
        self.assertEqual(4, len(current))
        delta_dates = sorted([str(d) for d in delta["Date"].to_list()])
        self.assertEqual(["2020-02-01", "2020-04-01"], delta_dates)
        feb = delta.filter(pl.col("Date") == pl.lit("2020-02-01").str.to_date())["Value"][0]
        self.assertEqual(2.5, feb)

    def test_state_cache_multiple_columns_changed(self):
        """Row with multiple changed columns appears exactly once in delta with current values."""
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
        """Previous always reflects the current from the immediately preceding run."""
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
        """Column added on a second run after baseline is established: propagated correctly."""
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
        """CTR_ACT_DELTA_COLUMNS counts unified-schema columns (current + update), not just update columns."""
        t = self._setup_state_test("test-6")
        t.state_cache(self._df([("2020-01-01", 9.0), ("2020-02-01", 9.0)]))
        self.assertEqual(2, t.get_counter(library.CTR_SRC_DATA, library.CTR_ACT_DELTA_COLUMNS))

    def test_state_cache_aggregate_called_twice(self):
        """Aggregate runs on update input and on merged current only; cached current is not re-aggregated."""
        t = self._setup_state_test("test-2")
        calls = [0]

        def counting(df):
            calls[0] += 1
            return df

        t.state_cache(self._df([("2020-03-01", 3.0)]), counting)
        self.assertEqual(2, calls[0])

    def test_state_cache_null_date_in_update(self):
        """Null-dated rows in update are silently dropped: they must not appear in current, delta, or CSV.

        Bug: equity's outer join (pre-Polars-1.x coalesce fix) produced null-dated rows that
        state_cache accepted and stored, causing equity_database_df.head(1).rows()[0][0] == None.
        Fix: state_cache now filters null dates from update before processing.
        """
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
        """CTR_ACT_PREVIOUS_COLUMNS equals the unified schema width, not the previous-file column count.

        Bug (surprising behaviour): when the update introduces more columns than exist in the
        stored previous current, state_cache expands the previous DataFrame to match the union
        schema before recording the counter.  The counter therefore reports the union width, not
        the width of the data that was actually persisted in the previous CSV.

        Equity hit this: the fixture __Equity_Current.csv had 171 data columns but after fixing
        all other bugs the update produced 207 columns, making CTR_ACT_PREVIOUS_COLUMNS == 207
        even though the file on disk only contained 171.
        """
        t = self._setup_state_test("test-4")
        update = pl.DataFrame({
            "Date": ["2020-01-01", "2020-02-01"],
            "Value": [1.0, 2.0],
            "Extra": [10.0, 20.0],
            "Third": [100.0, 200.0],
        }).with_columns(pl.col("Date").str.to_date())
        t.state_cache(update)
        # previous file had 1 data column (Value + Extra = 2 from test-4 fixture),
        # update adds Third → union = 3 data columns → counter = 3, not 2
        self.assertEqual(3, t.get_counter(library.CTR_SRC_DATA, library.CTR_ACT_PREVIOUS_COLUMNS))

    def test_state_cache_disable_downloads_returns_current_as_previous(self):
        """config.disable_downloads=True returns the same cached current DataFrame for both
        current and previous, so callers must not rely on previous reflecting a distinct prior run.

        Bug: equity and other callers that diff current vs previous to detect changes see zero
        differences on the download-disabled path, because both references point to identical data.
        """
        t = self._setup_state_test("test-5")
        library.config.disable_downloads = True
        update = self._df([("2020-04-01", 4.0)])
        delta, current, previous = t.state_cache(update)
        self.assertEqual(0, len(delta))
        self.assertEqual(len(current), len(previous))
        self.assertEqual(current["Date"].to_list(), previous["Date"].to_list())
        self.assertEqual(current["Value"].to_list(), previous["Value"].to_list())

    def test_state_cache_disable_downloads_aggregate_not_applied(self):
        """config.disable_downloads=True returns the cached CSV current without re-applying
        the aggregate function.  The CSV reflects the aggregate from the *previous* run, so
        aggregate-added columns are present but their values may be stale if the aggregate
        formula changed between runs.

        Bug: equity's _aggregate_function is not re-run on the cached current, meaning any
        cross-row derived values (e.g. rolling change dimensions) reflect the prior computation,
        not a fresh one against the current state.  A new column added only in the aggregate
        and not yet persisted to CSV will be absent entirely.
        """
        t = self._setup_state_test("test-5")
        t.state_cache(self._df([("2020-01-01", 1.0), ("2020-02-01", 2.0), ("2020-03-01", 3.0)]),
                      lambda df: df.with_columns((pl.col("Value") * 2).alias("Double")))
        t.reset_counters()
        library.config.disable_downloads = True
        _, current, _ = t.state_cache(
            self._df([("2020-04-01", 4.0)]),
            lambda df: df.with_columns((pl.col("Value") * 100).alias("Double"))
        )
        # aggregate is NOT re-run: "Double" is from the prior CSV (Value*2), not Value*100
        self.assertIn("Double", current.columns)
        self.assertEqual([2.0, 4.0, 6.0], current.sort("Date")["Double"].to_list())
        # the new date (2020-04-01) from update is also absent — update is entirely ignored
        dates = [str(d) for d in current["Date"].to_list()]
        self.assertNotIn("2020-04-01", dates)

    def _price_df(self, date_price_pairs, ticker="AAPL"):
        """Build a DataFrame: Date + ticker Price Close."""
        return pl.DataFrame({
            "Date": [p[0] for p in date_price_pairs],
            "{} Price Close".format(ticker): [float(p[1]) for p in date_price_pairs],
        }).with_columns(pl.col("Date").str.to_date())

    def _price_change_agg(self, ticker="AAPL"):
        """Aggregator: cast String/Null→Float64, compute 1d-change %, select output columns."""
        price_col = "{} Price Close".format(ticker)
        change_col = "{} Price Close 1d-Change Percentage".format(ticker)

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
        """First run: all rows in delta and current; aggregator adds derived change column; previous empty."""
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
        """Same data re-submitted: delta is empty; current values and counters reflect no change."""
        t = self._setup_state_test("agg-2")
        data = self._price_df([
            ("2020-01-01", 100.0), ("2020-02-01", 200.0), ("2020-03-01", 300.0),
        ])
        t.state_cache(data, self._price_change_agg())
        t.reset_counters()
        delta, current, _ = t.state_cache(data, self._price_change_agg())
        self.assertEqual(0, len(delta))
        self.assertEqual(3, len(current))
        self.assertEqual(0, t.get_counter(library.CTR_SRC_DATA, library.CTR_ACT_DELTA_ROWS))
        self.assertEqual(3, t.get_counter(library.CTR_SRC_DATA, library.CTR_ACT_CURRENT_ROWS))

    def test_state_cache_aggregate_cross_boundary(self):
        """Appended rows compute pct_change against prior-state rows: cross-boundary context is correct.

        If state_cache called the aggregator only on the update slice (without merging historical
        current first), the Apr row would have no predecessor and its change would be 0.0.
        The correct value (33.3333) proves the aggregator runs on the fully merged frame.
        """
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
        # Apr: (400-300)/300*100 = 33.3333; would be 0.0 without cross-boundary context
        self.assertEqual(33.3333, delta_sorted["AAPL Price Close 1d-Change Percentage"][0])
        # May: (600-400)/400*100 = 50.0
        self.assertEqual(50.0, delta_sorted["AAPL Price Close 1d-Change Percentage"][1])

    def test_state_cache_aggregate_narrows_columns(self):
        """Aggregator that selects a column subset: extra input columns absent from delta and current."""
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
        """All-null Float64 column survives CSV round-trip: String→Float64 cast ensures second run succeeds."""
        t = self._setup_state_test("agg-5")

        def agg_with_null_col(df):
            str_cols = [c for c, t in zip(df.columns, df.dtypes)
                        if str(t) in ('String', 'Utf8', 'Null') and c != 'Date']
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

        # On the second run state_cache reads the CSV where the all-null column is empty strings.
        # The aggregator's String→Float64 cast (and state_cache's type coercion) must handle it.
        delta2, current2, _ = t.state_cache(data, agg_with_null_col)
        self.assertEqual(0, len(delta2))
        self.assertEqual(pl.Float64, current2["AAPL Baseline Price Close"].dtype)

    def test_state_cache_csv_files_written(self):
        """All four state CSV files are written with expected row counts after two consecutive runs."""
        t = self._setup_state_test("agg-6")
        t.state_cache(self._price_df([
            ("2020-01-01", 100.0), ("2020-02-01", 200.0),
        ]), self._price_change_agg())
        self.assertTrue(isfile(join(t.input, "__Test_Current.csv")))
        self.assertTrue(isfile(join(t.input, "__Test_Update.csv")))
        self.assertTrue(isfile(join(t.input, "__Test_Delta.csv")))
        self.assertFalse(isfile(join(t.input, "__Test_Previous.csv")))
        t.reset_counters()
        t.state_cache(self._price_df([
            ("2020-01-01", 100.0), ("2020-02-01", 200.0),
            ("2020-03-01", 300.0), ("2020-04-01", 400.0),
        ]), self._price_change_agg())
        self.assertTrue(isfile(join(t.input, "__Test_Previous.csv")))
        self.assertEqual(4, len(t.csv_read(join(t.input, "__Test_Current.csv"))))
        self.assertEqual(2, len(t.csv_read(join(t.input, "__Test_Previous.csv"))))
        self.assertEqual(4, len(t.csv_read(join(t.input, "__Test_Update.csv"))))
        self.assertEqual(2, len(t.csv_read(join(t.input, "__Test_Delta.csv"))))

    def test_state_cache_row_and_column_counters(self):
        """State counters correctly reflect row and column counts across two runs."""
        t = self._setup_state_test("agg-7")
        t.state_cache(self._price_df([
            ("2020-01-01", 100.0), ("2020-02-01", 200.0), ("2020-03-01", 300.0),
        ]), self._price_change_agg())
        self.assertEqual(3, t.get_counter(library.CTR_SRC_DATA, library.CTR_ACT_CURRENT_ROWS))
        self.assertEqual(3, t.get_counter(library.CTR_SRC_DATA, library.CTR_ACT_UPDATE_ROWS))
        self.assertEqual(3, t.get_counter(library.CTR_SRC_DATA, library.CTR_ACT_DELTA_ROWS))
        self.assertEqual(0, t.get_counter(library.CTR_SRC_DATA, library.CTR_ACT_PREVIOUS_ROWS))
        self.assertEqual(2, t.get_counter(library.CTR_SRC_DATA, library.CTR_ACT_CURRENT_COLUMNS))
        t.reset_counters()
        t.state_cache(self._price_df([
            ("2020-01-01", 100.0), ("2020-02-01", 200.0), ("2020-03-01", 300.0),
            ("2020-04-01", 400.0),
        ]), self._price_change_agg())
        self.assertEqual(4, t.get_counter(library.CTR_SRC_DATA, library.CTR_ACT_CURRENT_ROWS))
        self.assertEqual(4, t.get_counter(library.CTR_SRC_DATA, library.CTR_ACT_UPDATE_ROWS))
        self.assertEqual(1, t.get_counter(library.CTR_SRC_DATA, library.CTR_ACT_DELTA_ROWS))
        self.assertEqual(3, t.get_counter(library.CTR_SRC_DATA, library.CTR_ACT_PREVIOUS_ROWS))

    def test_state_cache_aggregate_with_guard(self):
        """Null-fill aggregator: add column if absent then fill only null rows; existing values preserved.

        Mirrors equity.py's pattern after the null-fill refactor: ensure the derived column
        exists (adding a null column if needed), then fill rows where it is null while leaving
        non-null rows untouched.  Proves both that new rows are filled and that previously
        computed non-null values survive the CSV round-trip unchanged.
        """

        def null_fill_agg(df):
            str_cols = [c for c, t in zip(df.columns, df.dtypes)
                        if str(t) in ('String', 'Utf8', 'Null') and c != 'Date']
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
        # Jan/Feb: existing non-null values preserved through CSV round-trip
        self.assertEqual(10.0, sorted2["AAPL Derived"][0])
        self.assertEqual(20.0, sorted2["AAPL Derived"][1])
        # Mar: new row filled by null-fill
        self.assertEqual(30.0, sorted2["AAPL Derived"][2])

    def test_state_cache_aggregate_nullfill_backfills_historical_rows(self):
        """Null-fill backfills CSV rows whose derived column was null when new source data arrives.

        Scenario: run 1 seeds the CSV with null Derived values (simulating an old run that
        lacked the null-fill).  Run 2 submits only the new Mar row; Jan/Feb come only from
        the CSV.  The null-fill aggregator, called on the merged current, fills Jan/Feb in-place
        from their Price Close.  A presence-guard would leave them null.
        """

        def null_fill_agg(df):
            str_cols = [c for c, t in zip(df.columns, df.dtypes)
                        if str(t) in ('String', 'Utf8', 'Null') and c != 'Date']
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
            """Seeds CSV with explicit null Derived to simulate a prior presence-guard run."""
            if "AAPL Price Close" in df.columns:
                df = df.with_columns(pl.lit(None).cast(pl.Float64).alias("AAPL Derived"))
            out_cols = [c for c in ["Date", "AAPL Price Close", "AAPL Derived"] if c in df.columns]
            return df.select(out_cols)

        t = self._setup_state_test("agg-9")
        t.state_cache(self._price_df([("2020-01-01", 1.0), ("2020-02-01", 2.0)]), seed_agg)
        t.reset_counters()

        # Update contains only Mar; Jan/Feb arrive via CSV with null Derived
        delta, current2, _ = t.state_cache(self._price_df([("2020-03-01", 3.0)]), null_fill_agg)
        self.assertEqual(3, len(current2))
        sorted2 = current2.sort("Date")
        # Jan/Feb backfilled on merged-current agg call; a presence-guard would leave these null
        self.assertEqual(10.0, sorted2["AAPL Derived"][0])
        self.assertEqual(20.0, sorted2["AAPL Derived"][1])
        # Mar computed from update-slice agg call
        self.assertEqual(30.0, sorted2["AAPL Derived"][2])
        # All three rows changed (Jan/Feb: null→value, Mar: new)
        self.assertEqual(3, len(delta))

    def _mk_df(self, rows):
        """Build a (Date, Account ID, Balance) DataFrame for multi-key state_cache tests."""
        return pl.DataFrame({
            "Date": [r[0] for r in rows],
            "Account ID": [r[1] for r in rows],
            "Balance": [float(r[2]) for r in rows],
        }).with_columns(pl.col("Date").str.to_date())

    def test_state_cache_multi_key_first_run(self):
        """First run with two key columns: all rows appear in delta and current; previous is empty."""
        t = self._setup_state_test("mk-1")
        delta, current, previous = t.state_cache(
            self._mk_df([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]),
            key_columns=["Date", "Account ID"])
        self.assertEqual(2, len(delta))
        self.assertEqual(2, len(current))
        self.assertEqual(0, len(previous))

    def test_state_cache_multi_key_no_change(self):
        """Re-submitting identical (Date, Account ID) rows produces no delta on second call."""
        t = self._setup_state_test("mk-2")
        data = self._mk_df([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)])
        t.state_cache(data, key_columns=["Date", "Account ID"])
        t.reset_counters()
        delta, current, _ = t.state_cache(data, key_columns=["Date", "Account ID"])
        self.assertEqual(0, len(delta))
        self.assertEqual(2, len(current))

    def test_state_cache_multi_key_value_change(self):
        """Changed Balance for one (Date, Account ID) pair: delta contains only that row."""
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
        """New Account ID on an existing date: only that new row appears in delta."""
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
        """New date rows added for all accounts: only the new-date rows appear in delta."""
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
        """Mixed update: one changed, one new date/account, one unchanged — delta contains only changed+new."""
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
        """Duplicate (Date, Account ID) pairs in a single update: last occurrence wins."""
        t = self._setup_state_test("mk-7")
        delta, current, _ = t.state_cache(self._mk_df([
            ("2026-01-01", "acc-1", 100.0),
            ("2026-01-01", "acc-1", 999.0),
        ]), key_columns=["Date", "Account ID"])
        self.assertEqual(1, len(current))
        self.assertEqual(999.0, current["Balance"][0])
        self.assertEqual(1, len(delta))

    def test_state_cache_multi_key_update_supersedes_current(self):
        """Update value for an existing (Date, Account ID) supersedes the stored current value."""
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
        """Column counters subtract len(key_columns)=2, not 1, from the schema width."""
        t = self._setup_state_test("mk-9")
        t.state_cache(self._mk_df([("2026-01-01", "acc-1", 100.0)]),
                      key_columns=["Date", "Account ID"])
        self.assertEqual(1, t.get_counter(library.CTR_SRC_DATA, library.CTR_ACT_UPDATE_COLUMNS))
        self.assertEqual(1, t.get_counter(library.CTR_SRC_DATA, library.CTR_ACT_CURRENT_COLUMNS))
        self.assertEqual(1, t.get_counter(library.CTR_SRC_DATA, library.CTR_ACT_DELTA_COLUMNS))

    def test_state_cache_multi_key_clean(self):
        """config.clean=True with multi-key: deletes current and rebuilds from update; previous is empty."""
        t = self._setup_state_test("mk-10")
        t.state_cache(self._mk_df([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]),
                      key_columns=["Date", "Account ID"])
        t.reset_counters()
        library.config.clean = True
        delta, current, previous = t.state_cache(
            self._mk_df([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]),
            key_columns=["Date", "Account ID"])
        self.assertEqual(2, len(delta))
        self.assertEqual(2, len(current))
        self.assertEqual(0, len(previous))

    def test_state_cache_multi_key_disable_downloads(self):
        """config.disable_downloads=True with multi-key: returns empty delta and cached current."""
        t = self._setup_state_test("mk-11")
        t.state_cache(self._mk_df([("2026-01-01", "acc-1", 100.0), ("2026-01-01", "acc-2", 200.0)]),
                      key_columns=["Date", "Account ID"])
        t.reset_counters()
        library.config.disable_downloads = True
        delta, current, _ = t.state_cache(
            self._mk_df([("2026-01-01", "acc-1", 999.0)]),
            key_columns=["Date", "Account ID"])
        self.assertEqual(0, len(delta))
        self.assertEqual(2, len(current))

    def test_state_cache_multi_key_with_aggregate(self):
        """Aggregate function applies correctly to multi-key DataFrames."""
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
        """Null Date rows are silently dropped even with multi-key columns."""
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
        """Create a Test instance with an isolated input dir, pre-seeded from resources/state/{fixture}."""
        t = Test("Test", "SOME_NON_EXISTANT_GUID")
        t.input = abspath(join(DIR_ROOT, "target", "data", "state-{}".format(fixture)))
        shutil.rmtree(t.input, ignore_errors=True)
        os.makedirs(t.input)
        src = join(DIR_ROOT, "src/test/resources/state", fixture)
        if isdir(src):
            for fname in os.listdir(src):
                shutil.copy(join(src, fname), join(t.input, fname))
        library.config.clean = False
        library.config.disable_downloads = False
        return t

    def _df(self, date_value_pairs):
        """Build a two-column (Date, Value) polars DataFrame from a list of ('YYYY-MM-DD', float) pairs."""
        return pl.DataFrame({
            "Date": [p[0] for p in date_value_pairs],
            "Value": [float(p[1]) for p in date_value_pairs],
        }).with_columns(pl.col("Date").str.to_date())

    def run_module(self, module_name, tests_asserts, log="info", prepare_only=False, enable_rerun=True,
                   clean=False, disable_uploads=True, disable_downloads=False):
        library.config.log_level = log
        library.config.clean = clean
        library.config.disable_uploads = disable_uploads
        library.config.disable_downloads = disable_downloads
        library.database = None
        dir_target = join(DIR_ROOT, "target")
        if not isdir(dir_target):
            os.makedirs(dir_target)
        module = getattr(importlib.import_module("wrangle.plugin.{}".format(module_name)), module_name.title())()

        def load_caches(source, destination):
            shutil.rmtree(destination, ignore_errors=True)
            if isdir(source):
                shutil.copytree(source, destination)
            module.print_log("Files written from [{}] to [{}]".format(source, destination))

        def assert_counters(counters_this, counters_that):
            for counter_source in counters_this:
                for counter_action in counters_this[counter_source]:
                    if "counter_equals" in counters_that:
                        counter_equals = counters_that["counter_equals"]
                        if counter_source in counter_equals and counter_action in counter_equals[counter_source]:
                            self.assertEqual(counters_this[counter_source][counter_action],
                                             counter_equals[counter_source][counter_action],
                                             "Counter [{} {}] equals assertion failed [{}] != [{}]".format(
                                                 counter_source, counter_action,
                                                 counters_this[counter_source][counter_action],
                                                 counter_equals[counter_source][counter_action]))
                    if "counter_less" in counters_that:
                        counter_less = counters_that["counter_less"]
                        if counter_source in counter_less and counter_action in counter_less[counter_source]:
                            self.assertLessEqual(counters_this[counter_source][counter_action],
                                                 counter_less[counter_source][counter_action],
                                                 "Counter [{} {}] less than assertion failed [{}] >= [{}]".format(
                                                     counter_source, counter_action,
                                                     counters_this[counter_source][counter_action],
                                                     counter_less[counter_source][counter_action]))
                    if "counter_greater" in counters_that:
                        counter_greater = counters_that["counter_greater"]
                        if counter_source in counter_greater and counter_action in counter_greater[counter_source]:
                            self.assertGreaterEqual(counters_this[counter_source][counter_action],
                                                    counter_greater[counter_source][counter_action],
                                                    "Counter [{} {}] greater than assertion failed [{}] <= [{}]".format(
                                                        counter_source, counter_action,
                                                        counters_this[counter_source][counter_action],
                                                        counter_greater[counter_source][counter_action]))

        print("")
        for test in tests_asserts:
            load_caches(join(DIR_ROOT, "src/test/resources/data", module_name, test), module.input)
            counters = {}
            if not prepare_only:
                print("STARTING (run)     [{}]   [{}]".format(module_name.title(), test))
                module.run()
                print("FINISHED (run)     [{}]   [{}]\n".format(module_name.title(), test))
                assert_counters(module.get_counters(), tests_asserts[test])
                if enable_rerun:
                    module.reset_counters()
                    print("STARTING (no-op)   [{}]   [{}]".format(module_name.title(), test))
                    module.run()
                    print("FINISHED (no-op)   [{}]   [{}]\n\n".format(module_name.title(), test))
                    assert_counters(module.get_counters(), ASSERT_NOOP)
                    module.reset_counters()
                    print("STARTING (reload)   [{}]   [{}]".format(module_name.title(), test))
                    library.config.clean = True
                    module.run()
                    library.config.clean = clean
                    print("FINISHED (reload)   [{}]   [{}]\n\n".format(module_name.title(), test))
                    assert_counters(module.get_counters(), ASSERT_RELOAD)
        return counters

    def setUp(self):
        print("")
        shutil.rmtree(join(DIR_ROOT, "target", "data"), ignore_errors=True)
        os.makedirs(join(DIR_ROOT, "target", "data"))
        shutil.rmtree(join(DIR_ROOT, "target", "runtime-unit"), ignore_errors=True)
        os.makedirs(join(DIR_ROOT, "target", "runtime-unit"))
        reset_config(log="info")

    def tearDown(self):
        reset_config()


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
        library.CTR_SRC_SOURCES: {
            library.CTR_ACT_ERRORED: 0,
        },
        library.CTR_SRC_FILES: {
            library.CTR_ACT_ERRORED: 0,
        },
        library.CTR_SRC_DATA: {
            library.CTR_ACT_ERRORED: 0,
        },
        library.CTR_SRC_EGRESS: {
            library.CTR_ACT_ERRORED: 0,
        },
    },
    "counter_greater": {
        library.CTR_SRC_SOURCES: {
            library.CTR_ACT_DOWNLOADED: 0,
        },
        library.CTR_SRC_FILES: {
            library.CTR_ACT_PROCESSED: 0,
        },
        library.CTR_SRC_DATA: {
            library.CTR_ACT_CURRENT_ROWS: 0,
            library.CTR_ACT_UPDATE_ROWS: 0,
            library.CTR_ACT_DELTA_ROWS: 0,
        },
    },
}

ASSERT_NOOP = {
    "counter_equals": {
        library.CTR_SRC_SOURCES: {
            library.CTR_ACT_DOWNLOADED: 0,
            library.CTR_ACT_UPLOADED: 0,
            library.CTR_ACT_PERSISTED: 0,
            library.CTR_ACT_ERRORED: 0,
        },
        library.CTR_SRC_FILES: {
            library.CTR_ACT_PROCESSED: 0,
            library.CTR_ACT_ERRORED: 0,
        },
        library.CTR_SRC_DATA: {
            library.CTR_ACT_UPDATE_COLUMNS: 0,
            library.CTR_ACT_UPDATE_ROWS: 0,
            library.CTR_ACT_DELTA_COLUMNS: 0,
            library.CTR_ACT_DELTA_ROWS: 0,
            library.CTR_ACT_ERRORED: 0,
        },
        library.CTR_SRC_EGRESS: {
            library.CTR_ACT_QUEUE_COLUMNS: 0,
            library.CTR_ACT_QUEUE_ROWS: 0,
            library.CTR_ACT_SHEET_COLUMNS: 0,
            library.CTR_ACT_SHEET_ROWS: 0,
            library.CTR_ACT_DATABASE_COLUMNS: 0,
            library.CTR_ACT_DATABASE_ROWS: 0,
            library.CTR_ACT_ERRORED: 0,
        },
    },
    "counter_greater": {
        library.CTR_SRC_SOURCES: {
            library.CTR_ACT_CACHED: 0,
        },
        library.CTR_SRC_FILES: {
            library.CTR_ACT_SKIPPED: 0,
        },
    },
}

ASSERT_RELOAD = {
    "counter_equals": {
        library.CTR_SRC_SOURCES: {
            library.CTR_ACT_DOWNLOADED: 0,
            library.CTR_ACT_ERRORED: 0,
        },
        library.CTR_SRC_FILES: {
            library.CTR_ACT_ERRORED: 0,
        },
        library.CTR_SRC_DATA: {
            library.CTR_ACT_PREVIOUS_ROWS: 0,
            library.CTR_ACT_ERRORED: 0,
        },
        library.CTR_SRC_EGRESS: {
            library.CTR_ACT_ERRORED: 0,
        },
    },
    "counter_greater": {
        library.CTR_SRC_FILES: {
            library.CTR_ACT_PROCESSED: 0,
        },
        library.CTR_SRC_DATA: {
            library.CTR_ACT_CURRENT_ROWS: 0,
            library.CTR_ACT_UPDATE_ROWS: 0,
            library.CTR_ACT_DELTA_ROWS: 0,
        },
    },
}


class Test(Library):
    def _run(self):
        pass


if __name__ == '__main__':
    sys.argv.extend([__file__, "-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache"])
    sys.exit(pytest.main())
