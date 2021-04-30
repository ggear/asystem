import sys

sys.path.append('../../../main/python')

import os
import shutil
import unittest
import importlib
import pytest
import main
from wrangle import library
from mock import patch
import contextlib
import glob

DIR_TARGET = "../../../../target"
DIR_RESOURCES = "../../resources"
DIR_SRC = "../../../../src/main/python"


class WrangleTest(unittest.TestCase):

    def test_currency(self):
        self.run_module("currency", {"success_typical": ASSERT_RUN, }, write=False)

    def test_currency_all(self):
        self.run_module("currency", TEST_ASSERT_RUN)

    def test_equity(self):
        self.run_module("equity", {"success_typical": ASSERT_RUN, }, write=False)

    def test_equity_all(self):
        self.run_module("equity", TEST_ASSERT_RUN)

    def test_health(self):
        self.run_module("health", {"success_typical": ASSERT_RUN, }, write=False)

    def test_health_all(self):
        self.run_module("health", TEST_ASSERT_RUN)

    def test_interest(self):
        self.run_module("interest", {"success_typical": ASSERT_RUN, }, write=False)

    def test_interest_all(self):
        self.run_module("interest", TEST_ASSERT_RUN)

    # TODO: Re-enable once weather has been implemented
    # def test_weather(self):
    #     self.run_module("weather", {"success_typical": ASSERT_RUN, }, write=False)
    #
    # def test_weather_all(self):
    #     self.run_module("weather", TEST_ASSERT_RUN)

    def test_all(self):
        for module_path in glob.glob("{}/wrangle/*/*.py".format(DIR_SRC)):
            if not module_path.endswith("__init__.py"):
                self.run_module(os.path.basename(os.path.dirname(module_path)), {"success_fresh": {}, }, prepare_only=True, write=True)
        print("")
        self.assertEqual(main.main(), 0, "Main script ran with errors on first run")
        print("")
        self.assertEqual(main.main(), 0, "Main script ran with errors on second re-run")

    def run_module(self, module_name, tests_asserts, prepare_only=False, write=False):
        if not os.path.isdir(DIR_TARGET):
            os.makedirs(DIR_TARGET)
        module = getattr(importlib.import_module("wrangle.{}".format(module_name)), module_name.title())()

        def load_caches(source, destination):
            shutil.rmtree(destination, ignore_errors=True)
            if os.path.isdir(source):
                shutil.copytree(source, destination)

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
                            self.assertLess(counters_this[counter_source][counter_action],
                                            counter_less[counter_source][counter_action],
                                            "Counter [{} {}] less than assertion failed [{}] > [{}]".format(
                                                counter_source, counter_action,
                                                counters_this[counter_source][counter_action],
                                                counter_less[counter_source][counter_action]))
                    if "counter_greater" in counters_that:
                        counter_greater = counters_that["counter_greater"]
                        if counter_source in counter_greater and counter_action in counter_greater[counter_source]:
                            self.assertGreater(counters_this[counter_source][counter_action],
                                               counter_greater[counter_source][counter_action],
                                               "Counter [{} {}] greater than assertion failed [{}] < [{}]".format(
                                                   counter_source, counter_action,
                                                   counters_this[counter_source][counter_action],
                                                   counter_greater[counter_source][counter_action]))

        print("")
        for test in tests_asserts:
            load_caches("{}{}/{}".format(DIR_RESOURCES, module.input.split("target")[-1], test), module.input)
            counters = {}
            if not prepare_only:
                with patch.object(library.Library, "state_write") if not write else no_op():
                    with patch.object(library.Library, "sheet_write") if not write else no_op():
                        with patch.object(library.Library, "drive_write") if not write else no_op():
                            with patch.object(library.Library, "database_write") if not write else no_op():
                                print("STARTING           [{}]   [{}]".format(module_name.title(), test))
                                module.run()
                                print("FINISHED           [{}]   [{}]\n".format(module_name.title(), test))
                                assert_counters(module.get_counters(), tests_asserts[test])
                                module.reset_counters()
                                print("STARTING (re-run)  [{}]   [{}]".format(module_name.title(), test))
                                module.run()
                                print("FINISHED  (re-run) [{}]   [{}]\n\n".format(module_name.title(), test))
                                assert_counters(module.get_counters(), ASSERT_RERUN)
        return counters

    def setUp(self):
        pass

    def tearDown(self):
        pass


ASSERT_RUN = {
    "counter_equals": {
        library.CTR_SRC_RESOURCES: {
            library.CTR_ACT_ERRORED: 0,
        },
        library.CTR_SRC_FILES: {
            library.CTR_ACT_ERRORED: 0,
        },
        library.CTR_SRC_DATA: {
            library.CTR_ACT_ERRORED: 0,
        },
        library.CTR_SRC_EXPORT: {
            library.CTR_ACT_ERRORED: 0,
        },
    },
    "counter_greater": {
        library.CTR_SRC_RESOURCES: {
            library.CTR_ACT_DOWNLOADED: 0,
        },
        library.CTR_SRC_FILES: {
            library.CTR_ACT_PROCESSED: 0,
        },
        library.CTR_SRC_DATA: {
            library.CTR_ACT_CURRENT: 0,
            library.CTR_ACT_INPUT: 0,
            library.CTR_ACT_DELTA: 0,
        },
    },
}

ASSERT_RERUN = {
    "counter_equals": {
        library.CTR_SRC_RESOURCES: {
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
            library.CTR_ACT_PREVIOUS: 0,
            library.CTR_ACT_CURRENT: 0,
            library.CTR_ACT_INPUT: 0,
            library.CTR_ACT_DELTA: 0,
            library.CTR_ACT_ERRORED: 0,
        },
        library.CTR_SRC_EXPORT: {
            library.CTR_ACT_QUEUE: 0,
            library.CTR_ACT_SHEET: 0,
            library.CTR_ACT_DATABASE: 0,
            library.CTR_ACT_ERRORED: 0,
        },
    },
    "counter_greater": {
        library.CTR_SRC_RESOURCES: {
            library.CTR_ACT_CACHED: 0,
        },
        library.CTR_SRC_FILES: {
            library.CTR_ACT_SKIPPED: 0,
        },
    },
}

TEST_ASSERT_RUN = {
    "success_fresh": ASSERT_RUN,
    "success_partial": ASSERT_RUN,
    "success_typical": ASSERT_RUN,
}


@contextlib.contextmanager
def no_op():
    yield None


if __name__ == '__main__':
    sys.argv.extend([__file__, "-v", "--durations=50", "--cov=../../../main/python", "-o", "cache_dir=../../../../target/.pytest_cache"])
    pytest.main()
