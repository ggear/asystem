import sys

sys.path.append('../../../main/python')

import os
import shutil
import unittest
import importlib
import pytest
import main
from wrangle import script

DIR_TARGET = "../../../../target"
DIR_RESOURCES = "../../resources"


class WrangleTest(unittest.TestCase):

    def test_fund(self):
        self.run_module(
            "fund", counter_equals={
                script.CTR_SRC_FILES: {
                    script.CTR_ACT_ERRORED: 0
                },
                script.CTR_SRC_DATA: {
                    script.CTR_ACT_ERRORED: 0
                },
            })

    def test_interest(self):
        self.run_module(
            "interest", counter_equals={
                script.CTR_SRC_FILES: {
                    script.CTR_ACT_ERRORED: 0
                },
                script.CTR_SRC_DATA: {
                    script.CTR_ACT_ERRORED: 0
                },
            })

    def test_currency(self):
        self.run_module(
            "currency", counter_equals={
                script.CTR_SRC_FILES: {
                    script.CTR_ACT_ERRORED: 0
                },
                script.CTR_SRC_DATA: {
                    script.CTR_ACT_ERRORED: 0
                },
            })

    def test_all(self):
        self.run_module("fund", prepare_only=True)
        self.run_module("interest", prepare_only=True)
        self.run_module("fund", prepare_only=True)
        print("")
        self.assertEqual(main.main(), 0, "Main script ran with errors")

    def run_module(self, module_name, load_cache=True, counter_equals={}, counter_less={}, counter_greater={}, prepare_only=False):
        if not os.path.isdir(DIR_TARGET):
            os.makedirs(DIR_TARGET)
        module = getattr(importlib.import_module("wrangle.{}".format(module_name)), module_name.title())()
        shutil.rmtree(module.input, ignore_errors=True)
        if load_cache:
            shutil.copytree("{}/{}".format(DIR_RESOURCES, module.input.split("target")[-1]), module.input)
        shutil.rmtree(module.output, ignore_errors=True)
        counters = {}
        if not prepare_only:
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
        return counters


if __name__ == '__main__':
    sys.argv.extend([__file__, "-v", "--durations=50", "--cov=../../../main/python", "-o", "cache_dir=../../../../target/.pytest_cache"])
    pytest.main()
