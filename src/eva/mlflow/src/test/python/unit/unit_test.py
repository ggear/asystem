import sys
import unittest

import pytest

sys.path.append('../../../main/python')


class WrangleTest(unittest.TestCase):

    def test_adhoc(self):
        self.assertEqual(True, True)


if __name__ == '__main__':
    sys.argv.extend([__file__, "-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache"])
    sys.exit(pytest.main())
