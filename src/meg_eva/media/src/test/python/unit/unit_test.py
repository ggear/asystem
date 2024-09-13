import sys

sys.path.append('../../../main/python')

import os
import shutil
import unittest
import pytest
from media import analyse
from media import ingress
from os.path import *
from jproperties import Properties
import subprocess

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

from media.analyse import MEDIA_FILE_EXTENSIONS
from media.analyse import MEDIA_FILE_SCRIPTS


class InternetTest(unittest.TestCase):

    def test_analyse_simple(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "10/media/parents/movies/Kingdom Of Heaven (2005)"), scripts={})

    def test_analyse_crazy_chars(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "31/media"))
        self._test_analyse_assert(join(dir_test, "31/media"))

    def test_analyse_subtitles(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "22/media"))

    def test_analyse_duplicate(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "38/media"), scripts={})

    def test_analyse_ignore(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "35/media"))
        self._test_analyse_assert(join(dir_test, "35/media"))

    def test_analyse_rename(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "37/media"), scripts={"rename"})
        self._test_analyse_assert(join(dir_test, "37/media"), scripts={"rename"})
        self._test_analyse_assert(join(dir_test, "37/media"), scripts={"rename"})

    def test_analyse_scripts(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "34"), clean=True)
        self._test_analyse_assert(join(dir_test, "34/media"))
        self._test_analyse_assert(join(dir_test, "34"))

    def test_analyse_empty(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "39"), scripts={}, clean=True)
        self._test_analyse_assert(join(dir_test, "33"), scripts={})
        self._test_analyse_assert(join(dir_test, "39"), scripts={})

    def test_analyse_comprehensive(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "10"), scripts={"rename", "transcode"}, asserts=False, clean=True)
        self._test_analyse_assert(join(dir_test, "10/media"), scripts={"rename", "transcode"}, asserts=False)
        self._test_analyse_assert(join(dir_test, "10"), scripts={"rename", "transcode"}, asserts=False)
        for INDEX in {"31", "33", "34", "35", "37", "38", "39"}:
            self._test_analyse_assert(join(dir_test, INDEX), scripts={"rename", "transcode"})
            self._test_analyse_assert(join(dir_test, "{}/media".format(INDEX)), scripts={"rename", "transcode"})
            self._test_analyse_assert(join(dir_test, INDEX), scripts={"rename", "transcode"})

    def test_analyse_failures(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "some/non-existent/path"), expected=-1)
        self._test_analyse_assert("/tmp", expected=-2)
        self._test_analyse_assert(abspath(join(dir_test, "19/tmp")), expected=-3)
        self._test_analyse_assert(join(dir_test, "10/tmp"), expected=-4)

    def _test_analyse_assert(self, dir_test, expected=None, asserts=True,
                             scripts=MEDIA_FILE_SCRIPTS, extensions=MEDIA_FILE_EXTENSIONS, clean=False):

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
        actual = analyse._analyse(dir_test, sheet_guid, verbose=True)
        if expected is None:
            expected = _file_count()
        if asserts:
            self.assertEqual(expected, actual)
        if actual > 0:
            for script in scripts:
                file_count = _file_count()
                for file_root_dir, file_dirs, file_names in os.walk(dir_test):
                    for file_name in file_names:
                        if file_name == "{}.sh".format(script):
                            script_path = "\"{}\"".format( \
                                join(file_root_dir, file_name) \
                                    .replace("$", "\\$") \
                                    .replace("\"", "\\\""))
                            print("Running {} ...".format(script_path))
                            self.assertEqual(0, \
                                             subprocess.run([script_path], shell=True).returncode)
                self.assertGreaterEqual(_file_count(), file_count)

    def test_ingress_comprehensive_1(self):
        dir_test = self._test_prepare_dir("share_tmp_example", 1)
        self._test_ingress(dir_test, 171)

    def test_ingress_comprehensive_2(self):
        dir_test = self._test_prepare_dir("share_tmp_example", 2)
        self._test_ingress(dir_test, 1)

    def test_ingress_comprehensive_3(self):
        dir_test = self._test_prepare_dir("share_tmp_example", 3)
        self._test_ingress(dir_test, 7)

    def test_ingress_comprehensive_4(self):
        dir_test = self._test_prepare_dir("share_tmp_example", 4)
        self._test_ingress(dir_test, 5)

    def _test_ingress(self, dir_test, files_renamed):
        self.assertEqual(files_renamed, ingress._rename(join(dir_test, "1/tmp"), True))
        self.assertEqual(0, ingress._rename(join(dir_test, "1/tmp"), True))

    def _test_prepare_dir(self, label, index):
        dir_test = join(DIR_ROOT, "target/runtime-unit/{}_{}/share".format(label, index))
        dir_test_src = join(DIR_ROOT, "src/test/resources/{}_{}/share".format(label, index))
        print("")
        sys.stdout.flush()
        shutil.rmtree(dir_test, ignore_errors=True)
        os.makedirs(abspath(join(dir_test, "..")), exist_ok=True)
        shutil.copytree(dir_test_src, dir_test)
        return dir_test

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
