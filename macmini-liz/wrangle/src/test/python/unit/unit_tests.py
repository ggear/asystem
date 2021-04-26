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

ASSERT_DEFAULT = {"counter_equals": {
    library.CTR_SRC_DATA: {library.CTR_ACT_ERRORED: 0},
    library.CTR_SRC_FILES: {library.CTR_ACT_ERRORED: 0},
    library.CTR_SRC_RESOURCES: {library.CTR_ACT_ERRORED: 0},
}}

TEST_ASSERT_DEFAULT = {
    "success_fresh": ASSERT_DEFAULT,
    "success_partial": ASSERT_DEFAULT,
    "success_typical": ASSERT_DEFAULT,
}


class WrangleTest(unittest.TestCase):

    def test_currency(self):
        self.run_module("currency", {"success_typical": ASSERT_DEFAULT, }, write=False)

    def test_currency_all(self):
        self.run_module("currency", TEST_ASSERT_DEFAULT, write=False)

    def test_health(self):
        self.run_module("health", {"success_typical": ASSERT_DEFAULT, }, write=False)

    def test_health_all(self):
        self.run_module("health", TEST_ASSERT_DEFAULT, write=False)

    def test_equity(self):
        self.run_module("equity", {"success_typical": ASSERT_DEFAULT, }, write=False)

    def test_equity_all(self):
        self.run_module("equity", TEST_ASSERT_DEFAULT, write=False)

    def test_interest(self):
        self.run_module("interest", {"success_typical": ASSERT_DEFAULT, }, write=False)

    def test_interest_all(self):
        self.run_module("interest", TEST_ASSERT_DEFAULT, write=False)

    def test_weather(self):
        self.run_module("weather", {"success_typical": ASSERT_DEFAULT, }, write=False)

    def test_weather_all(self):
        self.run_module("weather", TEST_ASSERT_DEFAULT, write=False)

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

        print("")
        for test in tests_asserts:
            load_caches("{}{}/{}".format(DIR_RESOURCES, module.input.split("target")[-1], test), module.input)
            counters = {}
            if not prepare_only:
                with patch.object(library.Library, "state_write") if not write else no_op():
                    with patch.object(library.Library, "sheet_write") if not write else no_op():
                        with patch.object(library.Library, "drive_write") if not write else no_op():
                            with patch.object(library.Library, "database_write") if not write else no_op():
                                print("RUNNING    [{}]   [{}]".format(module_name.title(), test))
                                module.run()
                                module.print_counters()
                                counters = module.get_counters()
                                for counter_source in counters:
                                    for counter_action in counters[counter_source]:
                                        if "counter_equals" in tests_asserts[test]:
                                            counter_equals = tests_asserts[test]["counter_equals"]
                                            if counter_source in counter_equals and counter_action in counter_equals[counter_source]:
                                                self.assertEqual(counters[counter_source][counter_action],
                                                                 counter_equals[counter_source][counter_action],
                                                                 "Counter [{} {}] equals assertion failed [{}] != [{}]".format(
                                                                     counter_source, counter_action,
                                                                     counters[counter_source][counter_action],
                                                                     counter_equals[counter_source][counter_action]))
                                        if "counter_less" in tests_asserts[test]:
                                            counter_less = tests_asserts[test]["counter_less"]
                                            if counter_source in counter_less and counter_action in counter_less[counter_source]:
                                                self.assertLess(counters[counter_source][counter_action],
                                                                counter_less[counter_source][counter_action],
                                                                "Counter [{} {}] less than assertion failed [{}] > [{}]".format(
                                                                    counter_source, counter_action,
                                                                    counters[counter_source][counter_action],
                                                                    counter_less[counter_source][counter_action]))
                                        if "counter_greater" in tests_asserts[test]:
                                            counter_greater = tests_asserts[test]["counter_greater"]
                                            if counter_source in counter_greater and counter_action in counter_greater[counter_source]:
                                                self.assertGreater(counters[counter_source][counter_action],
                                                                   counter_greater[counter_source][counter_action],
                                                                   "Counter [{} {}] greater than assertion failed [{}] < [{}]".format(
                                                                       counter_source, counter_action,
                                                                       counters[counter_source][counter_action],
                                                                       counter_greater[counter_source][counter_action]))
                                module.reset_counters()
                                print("RE-RUNNING    [{}]   [{}]".format(module_name.title(), test))
                                module.run()
                                module.print_counters()
        return counters

    def setUp(self):
        pass

    def tearDown(self):
        pass


@contextlib.contextmanager
def no_op():
    yield None


if __name__ == '__main__':
    sys.argv.extend([__file__, "-v", "--durations=50", "--cov=../../../main/python", "-o", "cache_dir=../../../../target/.pytest_cache"])
    pytest.main()
