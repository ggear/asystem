import sys
import unittest
from os.path import abspath, dirname, join, realpath

import pytest

sys.path.append("../../../main/python")

from library import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))


class WrangleTest(unittest.TestCase):
    def test_init_env(self):
        self.assertEqual("/service/mlflow/artifacts", init_env()["MLFLOW_ARTIFACT_DIR"])


if __name__ == "__main__":
    sys.exit(
        pytest.main(
            [
                "-s",
                "-v",
                "--durations=50",
                "-o",
                f"cache_dir={join(DIR_ROOT, 'target/.pytest_cache')}",
                __file__,
            ]
        )
    )
