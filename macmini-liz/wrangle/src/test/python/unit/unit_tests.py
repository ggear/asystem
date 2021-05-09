import sys

sys.path.append('../../../main/python')
import copy
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

    def test_adhoc(self):
        self.run_module("health", {"success_fresh": ASSERT_RUN}, write=False)

    def test_currency_typical(self):
        self.run_module("currency", {"success_typical": merge_asserts(ASSERT_RUN, {
            "counter_equals": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_PREVIOUS_COLUMNS: 15,
                    library.CTR_ACT_CURRENT_COLUMNS: 15,
                    library.CTR_ACT_INPUT_COLUMNS: 15,
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
                    library.CTR_ACT_INPUT_COLUMNS: 15,
                    library.CTR_ACT_DELTA_COLUMNS: 15,
                },
            },
        })})

    def test_equity_typical(self):
        self.run_module("equity", {"success_typical": merge_asserts(ASSERT_RUN, {
            "counter_equals": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_PREVIOUS_COLUMNS: 108,
                    library.CTR_ACT_CURRENT_COLUMNS: 108,
                    library.CTR_ACT_INPUT_COLUMNS: 72,
                    library.CTR_ACT_DELTA_COLUMNS: 108,
                },
            },
        })})

    def test_equity_partial(self):
        self.run_module("equity", {"success_partial": merge_asserts(ASSERT_RUN, {
            "counter_equals": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_PREVIOUS_COLUMNS: 99,
                    library.CTR_ACT_CURRENT_COLUMNS: 108,
                    library.CTR_ACT_INPUT_COLUMNS: 108,
                    library.CTR_ACT_DELTA_COLUMNS: 108,
                },
            },
        })})

    def test_health_typical(self):
        self.run_module("health", {"success_typical": merge_asserts(ASSERT_RUN, {
            "counter_equals": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_PREVIOUS_COLUMNS: 88,
                    library.CTR_ACT_CURRENT_COLUMNS: 88,
                    library.CTR_ACT_INPUT_COLUMNS: 56,
                    library.CTR_ACT_DELTA_COLUMNS: 88,
                },
            },
        })})

    def test_health_partial(self):
        self.run_module("health", {"success_partial": merge_asserts(ASSERT_RUN, {
            "counter_equals": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_PREVIOUS_COLUMNS: 88,
                    library.CTR_ACT_CURRENT_COLUMNS: 88,
                    library.CTR_ACT_INPUT_COLUMNS: 64,
                    library.CTR_ACT_DELTA_COLUMNS: 88,
                },
            },
        })})

    def test_interest_typical(self):
        self.run_module("interest", {"success_typical": merge_asserts(ASSERT_RUN, {
            "counter_equals": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_PREVIOUS_COLUMNS: 15,
                    library.CTR_ACT_CURRENT_COLUMNS: 15,
                    library.CTR_ACT_INPUT_COLUMNS: 15,
                    library.CTR_ACT_DELTA_COLUMNS: 15,
                },
            },
        })})

    def test_interest_partial(self):
        self.run_module("interest", {"success_partial": merge_asserts(ASSERT_RUN, {
            "counter_equals": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_PREVIOUS_COLUMNS: 15,
                    library.CTR_ACT_CURRENT_COLUMNS: 15,
                    library.CTR_ACT_INPUT_COLUMNS: 15,
                    library.CTR_ACT_DELTA_COLUMNS: 15,
                },
            },
        })})

    def test_weather_typical(self):
        self.run_module("weather", {"success_typical": merge_asserts(ASSERT_RUN, {
            "counter_equals": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_PREVIOUS_COLUMNS: 0,
                    library.CTR_ACT_CURRENT_COLUMNS: 1,
                    library.CTR_ACT_INPUT_COLUMNS: 1,
                    library.CTR_ACT_DELTA_COLUMNS: 1,
                },
            },
        })})

    def test_weather_partial(self):
        self.run_module("weather", {"success_partial": merge_asserts(ASSERT_RUN, {
            "counter_equals": {
                library.CTR_SRC_DATA: {
                    library.CTR_ACT_PREVIOUS_COLUMNS: 0,
                    library.CTR_ACT_CURRENT_COLUMNS: 1,
                    library.CTR_ACT_INPUT_COLUMNS: 1,
                    library.CTR_ACT_DELTA_COLUMNS: 1,
                },
            },
        })})

    def test_all_fresh(self):
        for module_path in glob.glob("{}/wrangle/*/*.py".format(DIR_SRC)):
            if not module_path.endswith("__init__.py"):
                self.run_module(os.path.basename(os.path.dirname(module_path)), {"success_fresh": {}, }, prepare_only=True)
        with patch.object(library.Library, "stdout_write"):
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
                with patch.object(library.Library, "sheet_write") if not write else no_op():
                    with patch.object(library.Library, "database_write") if not write else no_op():
                        with patch.object(library.Library, "drive_write") if not write else no_op():
                            with patch.object(library.Library, "stdout_write"):
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
        library.CTR_SRC_EGRESS: {
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
            library.CTR_ACT_CURRENT_ROWS: 0,
            library.CTR_ACT_INPUT_ROWS: 0,
            library.CTR_ACT_DELTA_ROWS: 0,
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
            library.CTR_ACT_PREVIOUS_COLUMNS: 0,
            library.CTR_ACT_PREVIOUS_ROWS: 0,
            library.CTR_ACT_CURRENT_COLUMNS: 0,
            library.CTR_ACT_CURRENT_ROWS: 0,
            library.CTR_ACT_INPUT_COLUMNS: 0,
            library.CTR_ACT_INPUT_ROWS: 0,
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
        library.CTR_SRC_RESOURCES: {
            library.CTR_ACT_CACHED: 0,
        },
        library.CTR_SRC_FILES: {
            library.CTR_ACT_SKIPPED: 0,
        },
    },
}


@contextlib.contextmanager
def no_op():
    yield None


if __name__ == '__main__':
    sys.argv.extend([__file__, "-s", "-v", "--durations=50",
                     "--cov=../../../main/python", "-o", "cache_dir=../../../../target/.pytest_cache"])
    pytest.main()
