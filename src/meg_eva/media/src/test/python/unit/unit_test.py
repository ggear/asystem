import sys

sys.path.append('../../../main/python')

import os
import shutil
import unittest
import pytest
from media import analyse
from media import rename
from os.path import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))


class InternetTest(unittest.TestCase):

    def test_analyse_1(self):
        self._test_analyse(1, "1JHv8ytvcia-Nz2gvMcFfuOT_jDvTCO76BauY9gAWBQY", 27)

    def _test_analyse(self, index, sheet_guid, files_analysed):
        dir_test = join(DIR_ROOT, "target/runtime-unit/share_media_example_{}".format(index))
        dir_test_src = join(DIR_ROOT, "src/test/resources/share_media_example_{}".format(index))
        print("")
        sys.stdout.flush()
        shutil.rmtree(dir_test, ignore_errors=True)
        os.makedirs(abspath(join(dir_test, "..")), exist_ok=True)
        shutil.copytree(dir_test_src, dir_test)

        # TODO: Revert
        self.assertEqual(analyse._analyse(dir_test, sheet_guid, False), files_analysed)
        # self.assertEqual(analyse._analyse(dir_test, sheet_guid, True), files_analysed)
        # self.assertEqual(analyse._analyse(dir_test, sheet_guid, True, True), files_analysed)
        # self.assertEqual(analyse._analyse(dir_test, sheet_guid, True), files_analysed)

    def test_rename_1(self):
        self._test_rename(1, 171)

    def test_rename_2(self):
        self._test_rename(2, 1)

    def test_rename_3(self):
        self._test_rename(3, 7)

    def _test_rename(self, index, files_renamed):
        dir_test = join(DIR_ROOT, "target/runtime-unit/share_tmp_example_{}".format(index))
        dir_test_src = join(DIR_ROOT, "src/test/resources/share_tmp_example_{}".format(index))
        print("")
        sys.stdout.flush()
        shutil.rmtree(dir_test, ignore_errors=True)
        os.makedirs(abspath(join(dir_test, "..")), exist_ok=True)
        shutil.copytree(dir_test_src, dir_test)
        self.assertEqual(rename._rename(dir_test, True), files_renamed)
        self.assertEqual(rename._rename(dir_test, True), 0)


if __name__ == '__main__':
    sys.argv.extend([__file__, "-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache"])
    sys.exit(pytest.main())
