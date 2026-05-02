import sys

sys.path.append('../../../main/python')

import pytest


def test_warmup():
    print("")
    assert True


if __name__ == '__main__':
    sys.exit(pytest.main(["-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache", __file__, ]))
