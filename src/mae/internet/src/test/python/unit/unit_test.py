import sys

sys.path.append('../../../main/python')

import unittest
import pytest
from internet import main
from unittest.mock import patch, MagicMock


class InternetTest(unittest.TestCase):

    def test_all(self):
        print("")
        sys.stdout.flush()
        with patch("internet.main.query", MagicMock(return_value=[])):
            self.assertEqual(main.execute(), 0, "Script execution failed with non-zero return")


if __name__ == '__main__':
    sys.argv.extend([__file__, "-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache"])
    sys.exit(pytest.main())
