import sys

sys.path.append('../../../main/python')

import unittest
import pytest
from media import rename


class InternetTest(unittest.TestCase):

    def test_rename(self):
        print("")
        sys.stdout.flush()
        rename.rename("../../../../target/package/test/resources/share_tmp_example_1", "/tmp")


if __name__ == '__main__':
    sys.argv.extend([__file__, "-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache"])
    sys.exit(pytest.main())
