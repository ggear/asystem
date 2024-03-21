import contextlib
import copy
import importlib
import os
import shutil
import sys
import unittest
from datetime import datetime
from datetime import timedelta
from os.path import *

import polars as pl
import pytest
import pytz
from mock import patch

sys.path.append('../../../main/python')

from wrangle.plugin import library
from wrangle.plugin.library import Library

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

for key, value in list(library.load_profile(join(DIR_ROOT, ".env")).items()):
    os.environ[key] = value


class WrangleTest(unittest.TestCase):

    def test_adhoc(self):
        self.run_module("equity", {"success_typical": ASSERT_RUN},
                        disable_data_delta=False,
                        enable_data_subset=True,
                        disable_file_download=False,
                        disable_write_stdout=False,
                        enable_rerun=False,
                        enable_log=True,



                        enable_data_cache=False,  # TODO: Delete


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

    # def test_equity_typical(self):
    #     self.run_module("equity", {"success_typical": merge_asserts(ASSERT_RUN, {
    #         "counter_equals": {
    #             library.CTR_SRC_DATA: {
    #                 library.CTR_ACT_PREVIOUS_COLUMNS: 144,
    #             },
    #         },
    #         "counter_greater": {
    #             library.CTR_SRC_DATA: {
    #                 library.CTR_ACT_CURRENT_COLUMNS: 144,
    #                 library.CTR_ACT_UPDATE_COLUMNS: 108,
    #                 library.CTR_ACT_DELTA_COLUMNS: 144,
    #             },
    #         },
    #     })})
    #
    # def test_equity_partial(self):
    #     self.run_module("equity", {"success_partial": merge_asserts(ASSERT_RUN, {
    #         "counter_equals": {
    #             library.CTR_SRC_DATA: {
    #                 library.CTR_ACT_PREVIOUS_COLUMNS: 144,
    #             },
    #         },
    #         "counter_greater": {
    #             library.CTR_SRC_DATA: {
    #                 library.CTR_ACT_CURRENT_COLUMNS: 144,
    #                 library.CTR_ACT_UPDATE_COLUMNS: 126,
    #                 library.CTR_ACT_DELTA_COLUMNS: 144,
    #             },
    #         },
    #     })})

    # def test_health_typical(self):
    #     self.run_module("health", {"success_typical": merge_asserts(ASSERT_RUN, {
    #         "counter_equals": {
    #             library.CTR_SRC_DATA: {
    #                 library.CTR_ACT_PREVIOUS_COLUMNS: 99,
    #                 library.CTR_ACT_CURRENT_COLUMNS: 99,
    #                 library.CTR_ACT_DELTA_COLUMNS: 99,
    #             },
    #         },
    #         "counter_greater": {
    #             library.CTR_SRC_DATA: {
    #                 library.CTR_ACT_UPDATE_COLUMNS: 29,
    #             },
    #         },
    #     })})
    #
    # def test_health_partial(self):
    #     self.run_module("health", {"success_partial": merge_asserts(ASSERT_RUN, {
    #         "counter_equals": {
    #             library.CTR_SRC_DATA: {
    #                 library.CTR_ACT_PREVIOUS_COLUMNS: 99,
    #                 library.CTR_ACT_CURRENT_COLUMNS: 99,
    #                 library.CTR_ACT_DELTA_COLUMNS: 99,
    #             },
    #         },
    #         "counter_greater": {
    #             library.CTR_SRC_DATA: {
    #                 library.CTR_ACT_UPDATE_COLUMNS: 29,
    #             },
    #         },
    #     })})

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
    #
    # def test_library_adhoc(self):
    #     test = Test("Test", "SOME_NON_EXISTANT_GUID")
    #
    #     import pandas as pd
    #     from wrangle.plugin.equity import DRIVE_KEY
    #     from wrangle.plugin.equity import PANDAS_ENGINE
    #     from wrangle.plugin.equity import PANDAS_BACKEND
    #     equity_df_manual = test.sheet_read("Equity_manual", DRIVE_KEY, sheet_name="Manual",
    #                                        column_types={
    #                                            "MCK Price Close": "float64",
    #                                            "MCK Currency Rate Base": "float64",
    #                                        },
    #                                        write_cache=True,
    #                                        engine=PANDAS_ENGINE, dtype_backend=PANDAS_BACKEND)
    #     equity_df_manual.index = pd.to_datetime(equity_df_manual["Date"])
    #     del equity_df_manual["Date"]
    #     equity_df_manual = equity_df_manual.apply(pd.to_numeric)
    #     equity_df_manual = equity_df_manual.resample('D').interpolate(limit_direction='both', limit_area='inside').ffill()
    #     test.dataframe_print_pd(equity_df_manual, print_label="equity_manual_new", print_verb="processed",
    #                             print_suffix="into new dataframe")

    def test_library_sheet(self):
        test = Test("Test", "SOME_NON_EXISTANT_GUID")

        nonexist_name = "nonexist"
        nonexist_key = "!"
        nonexist_str = "[]"
        os.environ[library.WRANGLE_ENABLE_LOG] = "false"
        for data_df in [
            test.sheet_download(nonexist_name, nonexist_key, sheet_load_secs=0, sheet_retry_max=1, write_cache=True),
            test.sheet_download(nonexist_name, nonexist_key, sheet_load_secs=0, sheet_retry_max=1, write_cache=False),
            test.sheet_download(nonexist_name, nonexist_key, sheet_load_secs=0, sheet_retry_max=1, write_cache=True),
            test.sheet_download(nonexist_name, nonexist_key, sheet_load_secs=0, sheet_retry_max=1, write_cache=True, read_cache=False),
        ]:
            self.assertEqual(nonexist_str, test.dataframe_to_str(data_df))
            self.assertEqual(0, len(data_df))

        loading_name = "loading"
        loading_key = "1bUpZCIOM-olcxLQ7_fdgi4Nu7GOQC30sK_LALZ2B0bs"
        loading_str = "[]"
        os.environ[library.WRANGLE_ENABLE_LOG] = "false"
        for data_df in [
            test.sheet_download(loading_name, loading_key, sheet_load_secs=0, sheet_retry_max=1, write_cache=True),
            test.sheet_download(loading_name, loading_key, sheet_load_secs=0, sheet_retry_max=1, write_cache=False),
            test.sheet_download(loading_name, loading_key, sheet_load_secs=0, sheet_retry_max=1, write_cache=True),
            test.sheet_download(loading_name, loading_key, sheet_load_secs=0, sheet_retry_max=1, write_cache=True, read_cache=False),
        ]:
            self.assertEqual(loading_str, test.dataframe_to_str(data_df))
            self.assertEqual(0, len(data_df))

        empty_name = "empty"
        empty_key = "1nPtCOciS81Y-FWJZ8pi5-9Fd6RZ6_EqyfweBekFH6s4"
        test_column = {
            "My Column": pl.Utf8,
        }
        empty_str = "[]"
        empty_str_column = "[My Column(str)]"
        os.environ[library.WRANGLE_ENABLE_LOG] = "true"
        for data_df in [
            test.sheet_download(empty_name, empty_key, write_cache=True),
            test.sheet_download(empty_name, empty_key, write_cache=False),
            test.sheet_download(empty_name, empty_key, write_cache=True),
            test.sheet_download(empty_name, empty_key, write_cache=False, read_cache=False),
        ]:
            self.assertEqual(empty_str, test.dataframe_to_str(data_df))
            self.assertEqual(0, len(data_df))
        for data_df in [
            test.sheet_download(empty_name, empty_key, schema=test_column, write_cache=True),
            test.sheet_download(empty_name, empty_key, schema=test_column, write_cache=False),
            test.sheet_download(empty_name, empty_key, schema=test_column, write_cache=True),
            test.sheet_download(empty_name, empty_key, schema=test_column, write_cache=True, read_cache=False),
        ]:
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
        test_type_numeric = {
            "Integer": pl.Int64,
            "Integer with NULL": pl.Int64,
            "Float": pl.Float64,
            "Float with NULL": pl.Float64,
            "String": pl.Utf8,
            "String with NULL": pl.Utf8,
        }
        test_str = "[Integer({}), Integer with NULL({}), Float({}), Float with NULL({}), String({}), String with NULL({})]"
        test_str_utf = ["str" for _ in range(0, len(test_type_numeric))]
        test_str_numeric = [test.dataframe_type_to_str(dtype) for dtype in test_type_numeric.values()]
        os.environ[library.WRANGLE_ENABLE_LOG] = "true"
        for data_df in [
            test.sheet_download(test_name + "-1", test_key, sheet_start_row=3, write_cache=True),
            test.sheet_download(test_name + "-1", test_key, sheet_start_row=3, write_cache=False),
            test.sheet_download(test_name + "-1", test_key, sheet_start_row=3, write_cache=True),
            test.sheet_download(test_name + "-1", test_key, sheet_start_row=3, write_cache=True, read_cache=False),
            test.sheet_download(test_name + "-2", test_key, sheet_start_row=3, schema=test_type_numeric, write_cache=True),
            test.sheet_download(test_name + "-2", test_key, sheet_start_row=3, schema=test_type_numeric, write_cache=False),
            test.sheet_download(test_name + "-2", test_key, sheet_start_row=3, schema=test_type_numeric, write_cache=True),
            test.sheet_download(test_name + "-2", test_key, sheet_start_row=3, schema=test_type_numeric, write_cache=True,
                                read_cache=False),
        ]:
            self.assertEqual(test_str.format(*test_str_numeric), test.dataframe_to_str(data_df))
            self.assertEqual(4, len(data_df))
        for data_df in [
            test.sheet_download(test_name + "-3", test_key, sheet_start_row=3, schema=test_type_utf, write_cache=True),
            test.sheet_download(test_name + "-3", test_key, sheet_start_row=3, schema=test_type_utf, write_cache=False),
            test.sheet_download(test_name + "-3", test_key, sheet_start_row=3, schema=test_type_utf, write_cache=True),
            test.sheet_download(test_name + "-3", test_key, sheet_start_row=3, schema=test_type_utf, write_cache=True, read_cache=False),
        ]:
            self.assertEqual(test_str.format(*test_str_utf), test.dataframe_to_str(data_df))
            self.assertEqual(4, len(data_df))

        data_name = "Index_weights"
        data_key = "1Kf9-Gk7aD4aBdq2JCfz5zVUMWAtvJo2ZfqmSQyo8Bjk"
        data_type = {
            "Holdings Quantity": pl.Utf8,
        }
        data_str = "[Exchange Symbol(str), Holdings Quantity({}), Unit Price(f64), Watch Value(f64), Watch Quantity(f64), Baseline Quantity(i64)]"
        data_str_type = [test.dataframe_type_to_str(data_type[column]) for column in data_type]
        for data_df in [
            test.sheet_download(data_name + "-1", data_key, "Indexes", 2, write_cache=True),
            test.sheet_download(data_name + "-1", data_key, "Indexes", 2, write_cache=False),
            test.sheet_download(data_name + "-1", data_key, "Indexes", 2, write_cache=True),
            test.sheet_download(data_name + "-1", data_key, "Indexes", 2, write_cache=True, read_cache=False),
        ]:
            self.assertEqual(data_str.format("f64"), test.dataframe_to_str(data_df))
            self.assertEqual(19, len(data_df))
        for data_df in [
            test.sheet_download(data_name + "-1", data_key, "Indexes", 2, schema=data_type, write_cache=True),
            test.sheet_download(data_name + "-1", data_key, "Indexes", 2, schema=data_type, write_cache=False),
            test.sheet_download(data_name + "-1", data_key, "Indexes", 2, schema=data_type, write_cache=True),
            test.sheet_download(data_name + "-1", data_key, "Indexes", 2, schema=data_type, write_cache=True, read_cache=False),
        ]:
            self.assertEqual(data_str.format(*data_str_type), test.dataframe_to_str(data_df))
            self.assertEqual(19, len(data_df))

    def test_library_database(self):
        test = Test("Test", "SOME_NON_EXISTANT_GUID")

        # invalid_name = "invalid"
        # invalid_query = "!"
        # invalid_str = "[]"
        # os.environ[library.WRANGLE_ENABLE_LOG] = "false"
        # for data_df in [
        #     test.database_download(invalid_name, invalid_query, force=True),
        #     test.database_download(invalid_name, invalid_query, force=False),
        #     test.database_download(invalid_name, invalid_query, force=True),
        #     test.database_download(invalid_name, invalid_query, force=True, check=False),
        # ]:
        #     self.assertEqual(invalid_str, test.dataframe_to_str(data_df))
        #     self.assertEqual(0, len(data_df))
        #
        # empty_name = "empty"
        # empty_query = """
        #     from(bucket: "data_public")
        #       |> range(start: -10ms, stop: now())
        #       |> filter(fn: (r) => r._measurement == "a_non_existent_metric")
        # """
        # empty_type = {"Date": pl.Date}
        # empty_str = "[{}]"
        # os.environ[library.WRANGLE_ENABLE_LOG] = "true"
        # for data_df in [
        #     test.database_download(empty_name, empty_query, force=True),
        #     test.database_download(empty_name, empty_query, force=False),
        #     test.database_download(empty_name, empty_query, force=True),
        #     test.database_download(empty_name, empty_query, force=True, check=False),
        # ]:
        #     self.assertEqual(empty_str.format(""), test.dataframe_to_str(data_df))
        #     self.assertEqual(0, len(data_df))
        # for data_df in [
        #     test.database_download(empty_name, empty_query, schema=empty_type, force=True),
        #     test.database_download(empty_name, empty_query, schema=empty_type, force=False),
        #     test.database_download(empty_name, empty_query, schema=empty_type, force=True),
        #     test.database_download(empty_name, empty_query, schema=empty_type, force=True, check=False),
        # ]:
        #     self.assertEqual(empty_str.format("Date(date)"), test.dataframe_to_str(data_df))
        #     self.assertEqual(0, len(data_df))
        #
        # fx_name = "RBA_FX_GBP_rates"
        # fx_query = """
        #     from(bucket: "data_public")
        #     |> range(start: 1985-01-02T00:00:00+00:00, stop: now())
        #     |> filter(fn: (r) => r["_measurement"] == "currency")
        #     |> filter(fn: (r) => r["period"] == "1d")
        #     |> filter(fn: (r) => r["type"] == "snapshot")
        #     |> filter(fn: (r) => r["_field"] == "aud/gbp")
        #     |> keep(columns: ["_time", "_value"])
        #     |> sort(columns: ["_time"])
        #     |> unique(column: "_time")
        #     |> rename(columns: {_time: "Date", _value: "Rate"})
        # """
        # fx_type = {"Date": pl.Date, "Rate": pl.Float64}
        # fx_str = "[Date({}), Rate(f64)]"
        # os.environ[library.WRANGLE_ENABLE_LOG] = "true"
        # for data_df in [
        #     test.database_download(fx_name, fx_query, force=True),
        #     test.database_download(fx_name, fx_query, force=False),
        #     test.database_download(fx_name, fx_query, force=True),
        #     test.database_download(fx_name, fx_query, force=True, check=False),
        # ]:
        #     self.assertEqual(data_str.format("datetime[μs, UTC]"), test.dataframe_to_str(data_df))
        #     self.assertGreater(len(data_df), 6000)
        # for data_df in [
        #     test.database_download(fx_name, fx_query, schema=fx_type, force=True),
        #     test.database_download(fx_name, fx_query, schema=fx_type, force=False),
        #     test.database_download(fx_name, fx_query, schema=fx_type, force=True),
        #     test.database_download(fx_name, fx_query, schema=fx_type, force=True, check=False),
        # ]:
        #     self.assertEqual(fx_str.format("date"), test.dataframe_to_str(data_df))
        #     self.assertGreater(len(data_df), 6000)

        interest_name = join(DIR_ROOT, "target", "runtime-unit", "Bank_Interest_Rates.csv")
        interest_start = pytz.UTC.localize(datetime(1993, 1, 1))
        interest_end = pytz.UTC.localize(datetime(2023, 6, 1))
        interest_query = """
from(bucket: "data_public")
    |> range(start: {}, stop: {})
    |> filter(fn: (r) => r["_measurement"] == "interest")
    |> filter(fn: (r) => r["_field"] == "bank")
    |> filter(fn: (r) => r["period"] == "1mo")
    |> keep(columns: ["_time", "_value"])
    |> sort(columns: ["_time"])
    |> unique(column: "_time")
    |> rename(columns: {{_time: "Timestamp", _value: "Rate"}})
        """.format(interest_start.isoformat(), (interest_end + timedelta(1)).isoformat())
        interest_type = {"Date": pl.Date, "Rate": pl.Float64}
        interest_str = "[Date({}), Rate(f64)]"
        os.environ[library.WRANGLE_ENABLE_LOG] = "true"
        self.assertEqual((True, True),
                         test.database_download(interest_name, interest_query, end=interest_end))
        self.assertEqual((True, False),
                         test.database_download(interest_name, interest_query, end=interest_end))
        self.assertEqual((True, True),
                         test.database_download(interest_name, interest_query, end=interest_end, force=True))
        self.assertEqual((True, True),
                         test.database_download(interest_name, interest_query, end=interest_end + timedelta(1)))
        self.assertEqual((True, False),
                         test.database_download(interest_name, interest_query, end=interest_end + timedelta(1), check=False))

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
        df_data = [{"C1": 1, "C2": 1.1, "C3": "1"}, {"C1": 2, "C2": 2.2, "C3": "2"}, {"C1": None, "C2": None, "C3": None}]
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
        df_lots = [{"C{}".format(c): v * v / 0.2 for c in range(1, df_lots_cols + 1)} for v in range(1, df_lots_rows + 1)]
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

    #
    def run_module(self, module_name, tests_asserts, enable_log=True, prepare_only=False, enable_rerun=True,
                   enable_data_subset=False, enable_data_cache=False, disable_write_stdout=True,
                   disable_data_delta=False, disable_file_upload=True, disable_file_download=False):
        os.environ[library.WRANGLE_ENABLE_LOG] = str(enable_log)
        os.environ[library.WRANGLE_ENABLE_DATA_CACHE] = str(enable_data_cache)
        os.environ[library.WRANGLE_ENABLE_DATA_SUBSET] = str(enable_data_subset)
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
        shutil.rmtree(join(DIR_ROOT, "target", "data"), ignore_errors=True)
        os.makedirs(join(DIR_ROOT, "target", "data"))
        shutil.rmtree(join(DIR_ROOT, "target", "runtime-unit"), ignore_errors=True)
        os.makedirs(join(DIR_ROOT, "target", "runtime-unit"))
        os.environ[library.WRANGLE_ENABLE_LOG] = "true"
        os.environ[library.WRANGLE_ENABLE_DATA_SUBSET] = "false"
        os.environ[library.WRANGLE_ENABLE_DATA_CACHE] = "false"
        os.environ[library.WRANGLE_DISABLE_DATA_DELTA] = "false"
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
