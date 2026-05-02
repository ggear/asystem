import sys
import unittest

import pytest

sys.path.append('../../../main/python')

from library import *


class WrangleTest(unittest.TestCase):

    def test_init_env(self):
        self.assertEqual("/service/mlflow/artifacts", init_env()["MLFLOW_ARTIFACT_DIR"])


if __name__ == '__main__':
    sys.exit(pytest.main(["-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache", __file__, ]))
