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

DIR_TARGET = "../../../../target"
DIR_RESOURCES = "../../resources"


class WrangleTest(unittest.TestCase):

    def test_all(self):
        self.test_all_write(False)

    def test_all_write(self, write=True):
        self.run_module("currency", prepare_only=True, write=write)
        self.run_module("interest", prepare_only=True, write=write)
        self.run_module("equity", prepare_only=True, write=write)
        print("")
        self.assertEqual(main.main(), 0, "Main script ran with errors on first run")
        self.assertEqual(main.main(), 0, "Main script ran with errors on second re-run")

    def test_currency(self):
        self.test_currency_write(False)

    def test_currency_write(self, write=True):
        self.run_module(
            "currency", counter_equals={
                library.CTR_SRC_RESOURCES: {
                    library.CTR_ACT_ERRORED: 0
                },
                library.CTR_SRC_FILES: {
                    library.CTR_ACT_ERRORED: 0
                },
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_ERRORED: 0
                },
            }, write=write)

    def test_health(self):
        self.test_health_write(False)

    def test_health_write(self, write=True):
        self.run_module(
            "health", counter_equals={
                library.CTR_SRC_RESOURCES: {
                    library.CTR_ACT_ERRORED: 0
                },
                library.CTR_SRC_FILES: {
                    library.CTR_ACT_ERRORED: 0
                },
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_ERRORED: 0
                },
            }, write=write)

    def test_equity(self):
        self.test_equity_write(False)

    def test_equity_write(self, write=True):
        self.run_module(
            "equity", counter_equals={
                library.CTR_SRC_RESOURCES: {
                    library.CTR_ACT_ERRORED: 0
                },
                library.CTR_SRC_FILES: {
                    library.CTR_ACT_ERRORED: 0
                },
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_ERRORED: 0
                },
            }, write=write)

    def test_interest(self):
        self.test_interest_write(False)

    def test_interest_write(self, write=True):
        self.run_module(
            "interest", counter_equals={
                library.CTR_SRC_RESOURCES: {
                    library.CTR_ACT_ERRORED: 0
                },
                library.CTR_SRC_FILES: {
                    library.CTR_ACT_ERRORED: 0
                },
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_ERRORED: 0
                },
            }, write=write)

    def test_weather(self):
        self.test_weather_write()

    def test_weather_write(self, write=True):
        self.run_module(
            "weather", counter_equals={
                library.CTR_SRC_RESOURCES: {
                    library.CTR_ACT_ERRORED: 0
                },
                library.CTR_SRC_FILES: {
                    library.CTR_ACT_ERRORED: 0
                },
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_ERRORED: 0
                },
            }, write=write)

    def run_module(self, module_name, load_cache=True,
                   counter_equals={}, counter_less={}, counter_greater={}, prepare_only=False, write=False):
        if not os.path.isdir(DIR_TARGET):
            os.makedirs(DIR_TARGET)
        module = getattr(importlib.import_module("wrangle.{}".format(module_name)), module_name.title())()

        def load_caches(source, destination):
            shutil.rmtree(destination, ignore_errors=True)
            if load_cache:
                if os.path.isdir(source):
                    shutil.copytree(source, destination)

        load_caches("{}{}".format(DIR_RESOURCES, module.input.split("target")[-1]), module.input)
        load_caches("{}{}".format(DIR_RESOURCES, module.output.split("target")[-1]), module.output)
        counters = {}
        if not prepare_only:
            with patch.object(library.Library, "delta_write") if not write else no_op():
                with patch.object(library.Library, "sheet_write") if not write else no_op():
                    with patch.object(library.Library, "drive_write") if not write else no_op():
                        with patch.object(library.Library, "database_write") if not write else no_op():
                            print("")
                            module.run()
                            module.print_counters()
                            counters = module.get_counters()
                            for source in counters:
                                for action in counters[source]:
                                    if source in counter_equals and action in counter_equals[source]:
                                        self.assertEqual(counters[source][action], counter_equals[source][action],
                                                         "Counter [{} {}] equals assertion failed [{}] != [{}]".format(
                                                             source, action, counters[source][action], counter_equals[source][action]))
                                    if source in counter_less and action in counter_less[source]:
                                        self.assertLess(counters[source][action], counter_less[source][action],
                                                        "Counter [{} {}] less than assertion failed [{}] > [{}]".format(
                                                            source, action, counters[source][action], counter_less[source][action]))
                                    if source in counter_greater and action in counter_greater[source]:
                                        self.assertGreater(counters[source][action], counter_greater[source][action],
                                                           "Counter [{} {}] greater than assertion failed [{}] < [{}]".format(
                                                               source, action, counters[source][action], counter_greater[source][action]))
                            module.reset_counters()
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
