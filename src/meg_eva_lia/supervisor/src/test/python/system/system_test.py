import os
import unittest
from os.path import *

import pytest
import sys

sys.path.append('../../../main/python')

TIMEOUT_WARMUP = 30

with open(abspath("{}/../../../../.env".format(dirname(realpath(__file__)))), 'r') as profile_file:
    for profile_line in profile_file:
        if "=" in profile_line and not profile_line.startswith("#"):
            os.environ[profile_line.strip().split("=", 1)[0]] = profile_line.strip().split("=", 1)[1]


class MonitorTest(unittest.TestCase):

    def test_warmup(self):
        print("")
        assert True

    def test_first_run(self):
        print("")
        assert True

    def test_second_run(self):
        print("")
        assert True


if __name__ == '__main__':
    sys.argv.extend([__file__, "-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache"])
    sys.exit(pytest.main())
