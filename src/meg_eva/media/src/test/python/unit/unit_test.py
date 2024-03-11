import sys

sys.path.append('../../../main/python')

import os
import shutil
import unittest
import pytest
from media import rename
from os.path import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))


class InternetTest(unittest.TestCase):

    def test_rename_1(self):
        self._test(1)

    def test_rename_2(self):
        self._test(2)

    def test_rename_3(self):
        self._test(3)

    def _test(self, index):
        dir_test = join(DIR_ROOT, "target/runtime-unit/share_tmp_example_{}".format(index))
        dir_test_src = join(DIR_ROOT, "src/test/resources/share_tmp_example_{}".format(index))
        print("")
        sys.stdout.flush()
        shutil.rmtree(dir_test, ignore_errors=True)
        os.makedirs(abspath(join(dir_test, "..")), exist_ok=True)
        shutil.copytree(dir_test_src, dir_test)
        rename.rename(dir_test)
        rename.rename(dir_test)


if __name__ == '__main__':
    sys.argv.extend([__file__, "-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache"])
    sys.exit(pytest.main())
