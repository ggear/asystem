import contextlib
import copy
import importlib
import os
import shutil
import sys
import unittest
from collections import OrderedDict
from os.path import *

import pytest
from mock import patch
from pandas.api.extensions import no_default

sys.path.append('../../../main/python')

from wrangle.plugin import library
from wrangle.plugin.library import Library

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

for key, value in list(library.load_profile(join(DIR_ROOT, ".env")).items()):
    os.environ[key] = value


class WrangleTest(unittest.TestCase):

    def test_adhoc(self):
        self.run_module("equity", {"success_typical": ASSERT_RUN},
                        enable_log=True,
                        enable_rerun=False,
                        disable_data_delta=True,
                        disable_file_download=False,
                        enable_random_rows=False,
                        disable_write_stdout=True,
                        disable_file_upload=True,
                        disable_write_lineprotocol=True,
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
            "counter_equals": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_PREVIOUS_COLUMNS: 144,
                },
            },
            "counter_greater": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_CURRENT_COLUMNS: 144,
                    library.CTR_ACT_UPDATE_COLUMNS: 108,
                    library.CTR_ACT_DELTA_COLUMNS: 144,
                },
            },
        })})

    def test_equity_partial(self):
        self.run_module("equity", {"success_partial": merge_asserts(ASSERT_RUN, {
            "counter_equals": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_PREVIOUS_COLUMNS: 144,
                },
            },
            "counter_greater": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_CURRENT_COLUMNS: 144,
                    library.CTR_ACT_UPDATE_COLUMNS: 126,
                    library.CTR_ACT_DELTA_COLUMNS: 144,
                },
            },
        })})

    def test_health_typical(self):
        self.run_module("health", {"success_typical": merge_asserts(ASSERT_RUN, {
            "counter_equals": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_PREVIOUS_COLUMNS: 99,
                    library.CTR_ACT_CURRENT_COLUMNS: 99,
                    library.CTR_ACT_DELTA_COLUMNS: 99,
                },
            },
            "counter_greater": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_UPDATE_COLUMNS: 29,
                },
            },
        })})

    def test_health_partial(self):
        self.run_module("health", {"success_partial": merge_asserts(ASSERT_RUN, {
            "counter_equals": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_PREVIOUS_COLUMNS: 99,
                    library.CTR_ACT_CURRENT_COLUMNS: 99,
                    library.CTR_ACT_DELTA_COLUMNS: 99,
                },
            },
            "counter_greater": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_UPDATE_COLUMNS: 29,
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

    # TODO: Disable until weather wrangle is built
    # def test_weather_typical(self):
    #     self.run_module("weather", {"success_typical": merge_asserts(ASSERT_RUN, {
    #         "counter_equals": {
    #             library.CTR_SRC_DATA: {
    #                 library.CTR_ACT_PREVIOUS_COLUMNS: 0,
    #                 library.CTR_ACT_CURRENT_COLUMNS: 1,
    #                 library.CTR_ACT_UPDATE_COLUMNS: 1,
    #                 library.CTR_ACT_DELTA_COLUMNS: 1,
    #             },
    #         },
    #     })})
    #
    # def test_weather_partial(self):
    #     self.run_module("weather", {"success_partial": merge_asserts(ASSERT_RUN, {
    #         "counter_equals": {
    #             library.CTR_SRC_DATA: {
    #                 library.CTR_ACT_PREVIOUS_COLUMNS: 0,
    #                 library.CTR_ACT_CURRENT_COLUMNS: 1,
    #                 library.CTR_ACT_UPDATE_COLUMNS: 1,
    #                 library.CTR_ACT_DELTA_COLUMNS: 1,
    #             },
    #         },
    #     })})

    def test_library_adhoc(self):
        test = Test("Test", "SOME_NON_EXISTANT_GUID")

        import pandas as pd
        from wrangle.plugin.equity import DRIVE_KEY
        from wrangle.plugin.equity import PANDAS_ENGINE
        from wrangle.plugin.equity import PANDAS_BACKEND
        equity_df_manual = test.sheet_read("Equity_manual", DRIVE_KEY, sheet_name="Manual",
                                           column_types={
                                               "MCK Price Close": "float64",
                                               "MCK Currency Rate Base": "float64",
                                           },
                                           read_cache=library.test(library.WRANGLE_DISABLE_FILE_DOWNLOAD),
                                           engine=PANDAS_ENGINE, dtype_backend=PANDAS_BACKEND)
        equity_df_manual.index = pd.to_datetime(equity_df_manual["Date"])
        del equity_df_manual["Date"]
        equity_df_manual = equity_df_manual.apply(pd.to_numeric)
        equity_df_manual = equity_df_manual.resample('D').interpolate(limit_direction='both', limit_area='inside').ffill()
        test.dataframe_print(equity_df_manual, print_label="equity_manual_new", print_verb="processed", print_suffix="into new dataframe")

    def test_library_sheet(self):
        test = Test("Test", "SOME_NON_EXISTANT_GUID")

        nonexist_name = "nonexist"
        nonexist_key = "!"
        nonexist_str = "[Index(int64)]"
        os.environ[library.WRANGLE_ENABLE_LOG] = "false"
        for data_df in [
            test.sheet_read(nonexist_name, nonexist_key, sheet_load_secs=0, sheet_retry_max=1, read_cache=True, write_cache=True),
            test.sheet_read(nonexist_name, nonexist_key, sheet_load_secs=0, sheet_retry_max=1, read_cache=False, write_cache=True),
            test.sheet_read(nonexist_name, nonexist_key, sheet_load_secs=0, sheet_retry_max=1, read_cache=True, write_cache=True),
        ]:
            self.assertEqual(nonexist_str, test.dataframe_to_str(data_df))
            self.assertEqual(0, len(data_df))

        loading_name = "loading"
        loading_key = "1bUpZCIOM-olcxLQ7_fdgi4Nu7GOQC30sK_LALZ2B0bs"
        loading_str = "[Index(int64)]"
        os.environ[library.WRANGLE_ENABLE_LOG] = "false"
        for data_df in [
            test.sheet_read(loading_name, loading_key, sheet_load_secs=0, sheet_retry_max=1, read_cache=True, write_cache=True),
            test.sheet_read(loading_name, loading_key, sheet_load_secs=0, sheet_retry_max=1, read_cache=False, write_cache=True),
            test.sheet_read(loading_name, loading_key, sheet_load_secs=0, sheet_retry_max=1, read_cache=True, write_cache=True),
        ]:
            self.assertEqual(loading_str, test.dataframe_to_str(data_df))
            self.assertEqual(0, len(data_df))

        empty_name = "empty"
        empty_key = "1nPtCOciS81Y-FWJZ8pi5-9Fd6RZ6_EqyfweBekFH6s4"
        empty_str = "[Index(int64)]"
        os.environ[library.WRANGLE_ENABLE_LOG] = "true"
        for data_df in [
            test.sheet_read(empty_name, empty_key, read_cache=True, write_cache=True),
            test.sheet_read(empty_name, empty_key, read_cache=False, write_cache=True),
            test.sheet_read(empty_name, empty_key, read_cache=True, write_cache=True),
        ]:
            self.assertEqual(empty_str, test.dataframe_to_str(data_df))
            self.assertEqual(0, len(data_df))

        test_name = "test"
        test_key = "18MBAIWaQNVQBMESAISHIqLD11sRBz003x5OTH_Vt4SY"
        test_type_str = {
            "Integer": "string",
            "Integer with NULL": "string",
            "Float": "string",
            "Float with NULL": "string",
            "String": "string",
            "String with NULL": "string",
        }
        test_type_num = {
            "Integer": "int64",
            "Integer with NULL": "float64",
            "Float": "float64",
            "Float with NULL": "float64",
            "String": "object",
            "String with NULL": "object",
        }
        test_str = "[Index(int64),Integer({}),Integer with NULL({}),Float({}),Float with NULL({}),String({}),String with NULL({})]"
        test_str_types = [dtype for dtype in test_type_num.values()]
        test_str_string = ["string" for _ in range(0, len(test_type_num))]
        os.environ[library.WRANGLE_ENABLE_LOG] = "true"
        for data_df in [
            test.sheet_read(test_name + "-1", test_key, sheet_data_start=3, read_cache=True, write_cache=True),
            test.sheet_read(test_name + "-1", test_key, sheet_data_start=3, read_cache=False, write_cache=True),
            test.sheet_read(test_name + "-1", test_key, sheet_data_start=3, read_cache=True, write_cache=True),
            test.sheet_read(test_name + "-2", test_key, sheet_data_start=3, column_types=test_type_num, read_cache=True, write_cache=True),
            test.sheet_read(test_name + "-2", test_key, sheet_data_start=3, column_types=test_type_num, read_cache=False, write_cache=True),
            test.sheet_read(test_name + "-2", test_key, sheet_data_start=3, column_types=test_type_num, read_cache=True, write_cache=True),
        ]:
            self.assertEqual(test_str.format(*test_str_types), test.dataframe_to_str(data_df))
            self.assertEqual(4, len(data_df))
        for data_df in [
            test.sheet_read(test_name + "-3", test_key, sheet_data_start=3, column_types=test_type_str, read_cache=True, write_cache=True),
            test.sheet_read(test_name + "-3", test_key, sheet_data_start=3, column_types=test_type_str, read_cache=False, write_cache=True),
            test.sheet_read(test_name + "-3", test_key, sheet_data_start=3, column_types=test_type_str, read_cache=True, write_cache=True),
        ]:
            self.assertEqual(test_str.format(*test_str_string), test.dataframe_to_str(data_df))
            self.assertEqual(4, len(data_df))

        data_name = "Index_weights"
        data_key = "1Kf9-Gk7aD4aBdq2JCfz5zVUMWAtvJo2ZfqmSQyo8Bjk"
        data_str = "[Index(int64),Exchange Symbol(object),Holdings Quantity(float64),Unit Price(object),Watch Value(object),Watch Quantity(float64),Baseline Quantity(float64)]"
        for data_df in [
            test.sheet_read(data_name + "-1", data_key, sheet_name="Indexes", sheet_data_start=2, read_cache=True, write_cache=True),
            test.sheet_read(data_name + "-1", data_key, sheet_name="Indexes", sheet_data_start=2, read_cache=False, write_cache=True),
            test.sheet_read(data_name + "-1", data_key, sheet_name="Indexes", sheet_data_start=2, read_cache=True, write_cache=True),
        ]:
            self.assertEqual(data_str, test.dataframe_to_str(data_df))
            self.assertEqual(18, len(data_df))

    def test_library_database(self):
        test = Test("Test", "SOME_NON_EXISTANT_GUID")

        invalid_name = "invalid"
        invalid_query = "!"
        invalid_str = "[Index(int64)]"
        os.environ[library.WRANGLE_ENABLE_LOG] = "false"
        for data_df in [
            test.database_read(invalid_name, invalid_query, read_cache=True, write_cache=True),
            test.database_read(invalid_name, invalid_query, read_cache=False, write_cache=True),
            test.database_read(invalid_name, invalid_query, read_cache=True, write_cache=True),
        ]:
            self.assertEqual(invalid_str, test.dataframe_to_str(data_df))
            self.assertEqual(0, len(data_df))

        empty_name = "empty"
        empty_query = """
            from(bucket: "data_public")
              |> range(start: -10ms, stop: now())
              |> filter(fn: (r) => r._measurement == "a_non_existent_metric")
        """
        empty_type = {"Date": "int64"}
        empty_str = "[Index(int64){}]"
        os.environ[library.WRANGLE_ENABLE_LOG] = "true"
        for data_df in [
            test.database_read(empty_name, empty_query, read_cache=True, write_cache=True),
            test.database_read(empty_name, empty_query, read_cache=False, write_cache=True),
            test.database_read(empty_name, empty_query, read_cache=True, write_cache=True),
        ]:
            self.assertEqual(empty_str.format(""), test.dataframe_to_str(data_df))
            self.assertEqual(0, len(data_df))
        for data_df in [
            test.database_read(empty_name, empty_query, column_types=empty_type, read_cache=True, write_cache=True),
            test.database_read(empty_name, empty_query, column_types=empty_type, read_cache=False, write_cache=True),
            test.database_read(empty_name, empty_query, column_types=empty_type, read_cache=True, write_cache=True),
        ]:
            self.assertEqual(empty_str.format(",Date(int64)"), test.dataframe_to_str(data_df))
            self.assertEqual(0, len(data_df))

        data_name = "RBA_FX_GBP_rates"
        data_query = """
            from(bucket: "data_public")
            |> range(start: 1985-01-02T00:00:00+00:00, stop: now())
            |> filter(fn: (r) => r["_measurement"] == "currency")
            |> filter(fn: (r) => r["period"] == "1d")
            |> filter(fn: (r) => r["type"] == "snapshot")
            |> filter(fn: (r) => r["_field"] == "aud/gbp")
            |> keep(columns: ["_time", "_value"])
            |> sort(columns: ["_time"])
            |> unique(column: "_time")
            |> rename(columns: {_time: "Date", _value: "Rate"})
        """
        data_type = OrderedDict([("Date", "float128"), ("Rate", "float64")])
        data_str = "[Index(int64),Date({}),Rate(float64)]"
        os.environ[library.WRANGLE_ENABLE_LOG] = "true"
        for data_df in [
            test.database_read(data_name, data_query, read_cache=True, write_cache=True),
            test.database_read(data_name, data_query, read_cache=False, write_cache=True),
            test.database_read(data_name, data_query, read_cache=True, write_cache=True),
        ]:
            self.assertEqual(data_str.format("int64"), test.dataframe_to_str(data_df))
            self.assertGreater(len(data_df), 6000)
        for data_df in [
            test.database_read(data_name, data_query, column_types=data_type, read_cache=True, write_cache=True),
            test.database_read(data_name, data_query, column_types=data_type, read_cache=False, write_cache=True),
            test.database_read(data_name, data_query, column_types=data_type, read_cache=True, write_cache=True),
        ]:
            self.assertEqual(data_str.format("float128"), test.dataframe_to_str(data_df))
            self.assertGreater(len(data_df), 6000)

    def test_library_dataframe(self):
        test = Test("Test", "SOME_NON_EXISTANT_GUID")

        df_empty_str = "[Index(int64)]"
        df_empty_types = "[Index(int64),C2({})]"

        df_data_str = "[Index(int64),C1({}),C2({}),C3({})]"
        df_data_type = {"C2": "string"}
        df_data = [{"C1": 1, "C2": 1.1, "C3": "1"}, {"C1": 2, "C2": 2.2, "C3": "2"}, {"C1": 3, "C2": 3.3, "C3": "3"}]

        df_data_lots_cols = 50
        df_data_lots_rows = 100
        df_data_lots = [{"C{}".format(c): v * v / 0.2 for c in range(1, df_data_lots_cols + 1)} for v in range(1, df_data_lots_rows + 1)]

        self.assertEqual(df_empty_str,
                         test.dataframe_to_str(test.dataframe_new()))
        self.assertEqual(df_empty_str,
                         test.dataframe_to_str(test.dataframe_new([])))
        self.assertEqual(df_empty_str,
                         test.dataframe_to_str(test.dataframe_new([], [])))
        self.assertEqual(df_empty_str,
                         test.dataframe_to_str(test.dataframe_new([], [], {})))
        self.assertEqual(df_empty_str,
                         test.dataframe_to_str(test.dataframe_new([{}])))
        self.assertEqual(df_empty_str,
                         test.dataframe_to_str(test.dataframe_new([{}], [])))
        self.assertEqual(df_empty_str,
                         test.dataframe_to_str(test.dataframe_new([{}], [], {})))
        self.assertEqual(df_empty_str,
                         test.dataframe_to_str(test.dataframe_new([[]])))
        self.assertEqual(df_empty_str,
                         test.dataframe_to_str(test.dataframe_new([[]], [])))
        self.assertEqual(df_empty_str,
                         test.dataframe_to_str(test.dataframe_new([[]], [], {})))
        self.assertEqual(df_empty_str,
                         test.dataframe_to_str(test.dataframe_new(columns=[])))
        self.assertEqual(df_empty_str,
                         test.dataframe_to_str(test.dataframe_new(column_types={})))
        self.assertEqual(df_empty_str,
                         test.dataframe_to_str(test.dataframe_new(dtype_backend=no_default)))
        self.assertEqual(df_empty_str,
                         test.dataframe_to_str(test.dataframe_new(dtype_backend="numpy_nullable")))
        self.assertEqual(df_empty_str,
                         test.dataframe_to_str(test.dataframe_new(dtype_backend="pyarrow")))

        self.assertEqual(df_data_str.format("int64", "float64", "int64"),
                         test.dataframe_to_str(test.dataframe_new(df_data)))
        self.assertEqual(df_data_str.format("int64", "string", "int64"),
                         test.dataframe_to_str(test.dataframe_new(df_data, [], df_data_type)))
        self.assertEqual(df_empty_types.format("string"),
                         test.dataframe_to_str(test.dataframe_new(column_types=df_data_type)))

        self.assertEqual(df_data_str.format("int64", "float64", "int64"),
                         test.dataframe_to_str(test.dataframe_new(df_data, dtype_backend=no_default)))
        self.assertEqual(df_data_str.format("int64", "string", "int64"),
                         test.dataframe_to_str(test.dataframe_new(df_data, [], df_data_type, dtype_backend=no_default)))
        self.assertEqual(df_empty_types.format("string"),
                         test.dataframe_to_str(test.dataframe_new(column_types=df_data_type, dtype_backend=no_default)))

        self.assertEqual(df_data_str.format("Int64", "Float64", "Int64"),
                         test.dataframe_to_str(test.dataframe_new(df_data, dtype_backend="numpy_nullable")))
        self.assertEqual(df_data_str.format("Int64", "string", "Int64"),
                         test.dataframe_to_str(test.dataframe_new(df_data, [], df_data_type, dtype_backend="numpy_nullable")))
        self.assertEqual(df_empty_types.format("string"),
                         test.dataframe_to_str(test.dataframe_new(column_types=df_data_type, dtype_backend="numpy_nullable")))

        self.assertEqual(df_data_str.format("int64[pyarrow]", "double[pyarrow]", "int64[pyarrow]"),
                         test.dataframe_to_str(test.dataframe_new(df_data, dtype_backend="pyarrow")))
        self.assertEqual(df_data_str.format("int64[pyarrow]", "string[pyarrow]", "int64[pyarrow]"),
                         test.dataframe_to_str(test.dataframe_new(df_data, [], df_data_type, dtype_backend="pyarrow")))
        self.assertEqual(df_empty_types.format("string"),
                         test.dataframe_to_str(test.dataframe_new(column_types=df_data_type, dtype_backend="pyarrow")))

        self.assertEqual(True,
                         isinstance(test.dataframe_to_str(test.dataframe_new(column_types=df_data_type, print_label="lots")), str))
        self.assertEqual(True,
                         isinstance(test.dataframe_to_str(test.dataframe_new(df_data_lots, print_label="lots")), str))
        self.assertEqual(True,
                         isinstance(test.dataframe_to_str(test.dataframe_new(df_data_lots, print_label="lots"), False), list))

        self.assertEqual(df_data_lots_rows + 3,
                         len(test.dataframe_to_str(test.dataframe_new(df_data_lots, print_label="lots"), False, 100, 100)))
        self.assertEqual(0 + 4,
                         len(test.dataframe_to_str(test.dataframe_new(df_data_lots, print_label="lots"), False, 0, 0)))
        self.assertEqual(5 + 4,
                         len(test.dataframe_to_str(test.dataframe_new(df_data_lots, print_label="lots"), False, 5, 0)))
        self.assertEqual(5 + 4,
                         len(test.dataframe_to_str(test.dataframe_new(df_data_lots, print_label="lots"), False, 0, 5)))
        self.assertEqual(10 + 4,
                         len(test.dataframe_to_str(test.dataframe_new(df_data_lots, print_label="lots"), False, 5, 5)))

        self.assertEqual(3,
                         len((test.dataframe_new(df_data, column_types={"SOME UNKNOWN COLUMN": "float64"}))))
        self.assertEqual(3,
                         len((test.dataframe_new(df_data, column_types={"C1": "SOME_UKNOWN_TYPE"}))))
        self.assertEqual(3,
                         len((test.dataframe_new(df_data, column_types={column: "string" for column in df_data[0]}))))
        self.assertEqual(3,
                         len((test.dataframe_new(df_data, column_types={column: "SOME_UKNOWN_TYPE" for column in df_data[0]}))))

    #
    def run_module(self, module_name, tests_asserts, enable_log=True, prepare_only=False, enable_rerun=True, enable_random_rows=False,
                   disable_write_lineprotocol=False, disable_write_stdout=True, disable_data_delta=False, disable_file_upload=True,
                   disable_file_download=False):
        os.environ[library.WRANGLE_ENABLE_LOG] = str(enable_log)
        os.environ[library.WRANGLE_ENABLE_RANDOM_ROWS] = str(enable_random_rows)
        os.environ[library.WRANGLE_DISABLE_DATA_DELTA] = str(disable_data_delta)
        os.environ[library.WRANGLE_DISABLE_FILE_UPLOAD] = str(disable_file_upload)
        os.environ[library.WRANGLE_DISABLE_FILE_DOWNLOAD] = str(disable_file_download)
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
                with patch.object(library.Library, "dataframe_to_lineprotocol") if disable_write_lineprotocol else no_op():
                    with patch.object(library.Library, "sheet_write") if disable_file_upload else no_op():
                        with patch.object(library.Library, "drive_write") if disable_file_upload else no_op():
                            with patch.object(library.Library, "stdout_write") if disable_write_stdout else no_op():
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
                                    os.environ['WRANGLE_DISABLE_DATA_DELTA'] = 'true'
                                    module.run()
                                    os.environ['WRANGLE_DISABLE_DATA_DELTA'] = 'false'
                                    print("FINISHED (reload)   [{}]   [{}]\n\n".format(module_name.title(), test))
                                    assert_counters(module.get_counters(), ASSERT_RELOAD)
        return counters

    def setUp(self):
        print("")
        shutil.rmtree(join(DIR_ROOT, "target/data"), ignore_errors=True)
        os.makedirs(join(DIR_ROOT, "target/data"))
        os.environ[library.WRANGLE_ENABLE_LOG] = "true"
        os.environ[library.WRANGLE_ENABLE_RANDOM_ROWS] = "false"
        os.environ[library.WRANGLE_DISABLE_DATA_DELTA] = "true"
        os.environ[library.WRANGLE_DISABLE_FILE_UPLOAD] = "true"
        os.environ[library.WRANGLE_DISABLE_FILE_DOWNLOAD] = "false"

    def tearDown(self):
        pass


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


@contextlib.contextmanager
def no_op():
    yield None


class Test(Library):
    def _run(self):
        pass


if __name__ == '__main__':
    sys.argv.extend([__file__, "-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache"])
    sys.exit(pytest.main())
