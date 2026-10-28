import sys
from os.path import abspath, dirname, join, realpath

sys.path.append("../../../main/python")

import pytest

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))


def test_warmup():
    print()
    assert True


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
