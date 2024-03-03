import sys

sys.path.append('../../../main/python')

import os
import shutil
import unittest
import pytest
from media import rename
from os.path import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
DIR_TEST_1 = join(DIR_ROOT, "target/runtime-unit/share_tmp_example_1")
DIR_TEST_SRC_1 = join(DIR_ROOT, "src/test/resources/share_tmp_example_1")
DIR_TEST_2 = join(DIR_ROOT, "target/runtime-unit/share_tmp_example_2")
DIR_TEST_SRC_2 = join(DIR_ROOT, "src/test/resources/share_tmp_example_2")


class InternetTest(unittest.TestCase):

    def test_rename_1(self):
        print("")
        sys.stdout.flush()
        shutil.rmtree(DIR_TEST_1, ignore_errors=True)
        os.makedirs(abspath(join(DIR_TEST_1, "..")), exist_ok=True)
        shutil.copytree(DIR_TEST_SRC_1, DIR_TEST_1)
        rename.rename(DIR_TEST_1)
        rename.rename(DIR_TEST_1)

    def test_rename_2(self):
        print("")
        sys.stdout.flush()
        shutil.rmtree(DIR_TEST_2, ignore_errors=True)
        os.makedirs(abspath(join(DIR_TEST_2, "..")), exist_ok=True)
        shutil.copytree(DIR_TEST_SRC_2, DIR_TEST_2)
        rename.rename(DIR_TEST_2)
        rename.rename(DIR_TEST_2)


if __name__ == '__main__':
    sys.argv.extend([__file__, "-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache"])
    sys.exit(pytest.main())
