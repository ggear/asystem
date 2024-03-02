import sys

sys.path.append('../../../main/python')

import os
import shutil
import unittest
import pytest
from media import rename
from os.path import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
DIR_TEST = join(DIR_ROOT, "target/runtime-unit/share_tmp_example_1")
DIR_TEST_SRC = join(DIR_ROOT, "src/test/resources/share_tmp_example_1")


class InternetTest(unittest.TestCase):

    def test_rename(self):
        print("")
        sys.stdout.flush()
        shutil.rmtree(DIR_TEST, ignore_errors=True)
        os.makedirs(abspath(join(DIR_TEST, "..")), exist_ok=True)
        shutil.copytree(DIR_TEST_SRC, DIR_TEST)
        rename.rename(DIR_TEST)


if __name__ == '__main__':
    sys.argv.extend([__file__, "-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache"])
    sys.exit(pytest.main())
