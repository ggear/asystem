import sys

sys.path.append('../../../main/python')

import os
import shutil
import unittest
import pytest
from media import analyse
from media import rename
from os.path import *
from jproperties import Properties
import subprocess

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

from media.analyse import MEDIA_FILE_EXTENSIONS


class InternetTest(unittest.TestCase):

    def test_analyse_1(self):
        dir_test = self._test_analyse_dir(1)
        self._test_analyse_assert(join(dir_test, "10/media/docos/movies/The Bad News Bears (1976)"), 1)

    def test_analyse_2(self):
        dir_test = self._test_analyse_dir(1)
        self._test_analyse_assert(join(dir_test, "some/non-existent/path"), -1)
        self._test_analyse_assert("/tmp", -2)
        self._test_analyse_assert(abspath(join(dir_test, "19/tmp")), -3)
        self._test_analyse_assert(join(dir_test, "10/tmp"), -4)

    def test_analyse_3(self):
        dir_test = self._test_analyse_dir(1)
        self._test_analyse_assert(join(dir_test, "10/media/docos/movies/The Bad News Bears (1976)"), 1, clean=True)
        self._test_analyse_assert(join(dir_test, "31"))
        self._test_analyse_assert(join(dir_test, "33"))
        self._test_analyse_assert(join(dir_test, "10/media/parents/movies/Kingdom of Heaven (2005)"), 1)
        self._test_analyse_assert(join(dir_test, "10/media/comedy/movies"), 1)
        self._test_analyse_assert(join(dir_test, "10"), 60)
        self._test_analyse_assert(join(dir_test, "33"))
        self._test_analyse_assert(join(dir_test, "31"))
        self._test_analyse_assert(join(dir_test, "33"))

    def _test_analyse_dir(self, index):
        dir_test = join(DIR_ROOT, "target/runtime-unit/share_media_example_{}/share".format(index))
        dir_test_src = join(DIR_ROOT, "src/test/resources/share_media_example_{}/share".format(index))
        print("")
        sys.stdout.flush()
        shutil.rmtree(dir_test, ignore_errors=True)
        os.makedirs(abspath(join(dir_test, "..")), exist_ok=True)
        shutil.copytree(dir_test_src, dir_test)
        return dir_test

    def _test_analyse_assert(self, dir_test,
                             expected=None, extensions=MEDIA_FILE_EXTENSIONS, clean=False, scripts=True):

        def _file_count():
            file_count = 0
            for file_root_dir, file_dirs, file_names in os.walk(dir_test):
                for file_name in file_names:
                    if splitext(file_name)[1].replace(".", "") in extensions:
                        file_count += 1
            return file_count

        sheet_guid = os.getenv("MEDIA_GOOGLE_SHEET_GUID")
        if clean:
            self.assertEqual(0, analyse._analyse("/share", sheet_guid, clean=True, verbose=True))
        if expected is None:
            expected = _file_count()
        actual = analyse._analyse(dir_test, sheet_guid, verbose=True)
        self.assertEqual(expected, actual)
        if actual > 0 and scripts:
            file_count = _file_count()
            for file_root_dir, file_dirs, file_names in os.walk(dir_test):
                for file_name in file_names:
                    if file_name == "transcode.sh":
                        script_transcode = "'{}'".format(join(file_root_dir, file_name))
                        print("Running {} ...".format(script_transcode))
                        self.assertEqual(0, subprocess.run([script_transcode], shell=True).returncode)
            self.assertGreaterEqual(_file_count(), file_count)

    def test_rename_1(self):
        self._test_rename(1, 171)

    def test_rename_2(self):
        self._test_rename(2, 1)

    def test_rename_3(self):
        self._test_rename(3, 7)

    def _test_rename(self, index, files_renamed):
        dir_test = join(DIR_ROOT, "target/runtime-unit/share_tmp_example_{}".format(index))
        dir_test_src = join(DIR_ROOT, "src/test/resources/share_tmp_example_{}".format(index))
        print("")
        sys.stdout.flush()
        shutil.rmtree(dir_test, ignore_errors=True)
        os.makedirs(abspath(join(dir_test, "..")), exist_ok=True)
        shutil.copytree(dir_test_src, dir_test)
        self.assertEqual(files_renamed, rename._rename(dir_test, True))
        self.assertEqual(0, rename._rename(dir_test, True))

    @classmethod
    def setUp(_class):
        configs = Properties()
        with open(join(DIR_ROOT, ".env"), 'rb') as config_file:
            configs.load(config_file)
            for key in configs.keys():
                os.environ[key] = configs.get(key).data


if __name__ == '__main__':
    sys.argv.extend([__file__, "-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache"])
    sys.exit(pytest.main())
