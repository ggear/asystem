import sys

sys.path.append('../../../main/python')

import os
from pathlib import Path
import shutil
import unittest
import pytest
from media import analyse
from media.analyse import get_file_actions_dict as actions
from media import ingress
from os.path import *
from jproperties import Properties
import subprocess
import time

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

from media.analyse import MEDIA_FILE_EXTENSIONS
from media.analyse import MEDIA_FILE_SCRIPTS


class InternetTest(unittest.TestCase):

    def test_analyse_simple(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "10/media/parents/movies/Kingdom Of Heaven (2005)"),
                                  files_action_expected=actions(downscale=1), scripts={})

    def test_analyse_subtitles(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "22/media"),
                                  files_action_expected=actions(delete=1), scripts={})

    def test_analyse_containers(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "43/media"),
                                  files_action_expected=actions(delete=2), scripts={})

    def test_analyse_corrupt(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "32/media"),
                                  files_action_expected=actions(rename=2, delete=6, merge=2, upscale=5), scripts={})

    def test_analyse_duplicate(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "38/media"),
                                  files_action_expected=actions(rename=1, delete=8, merge=8, downscale=3, upscale=2), scripts={})

    def test_analyse_crazy_chars(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "31/media"),
                                  files_action_expected=actions(rename=1), scripts={})
        self._test_analyse_assert(join(dir_test, "31/media"),
                                  files_action_expected=actions(rename=1), scripts={"rename"})
        self._test_analyse_assert(join(dir_test, "31/media"),
                                  files_action_expected=actions(merge=0, downscale=1), scripts={"rename"})

    def test_analyse_ignore(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "35/media"),
                                  files_action_expected=actions(rename=2, delete=1, merge=1, downscale=2), scripts={})

    def test_analyse_rename(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "37/media"),
                                  files_action_expected=actions(rename=47, merge=5, upscale=7, downscale=4), scripts={"rename"})
        self._test_analyse_assert(join(dir_test, "37/media"),
                                  files_action_expected=actions(rename=19, delete=8, merge=5, downscale=2, upscale=29), scripts={"rename"})
        self._test_analyse_assert(join(dir_test, "37/media"),
                                  files_action_expected=actions(rename=19, delete=8, merge=5, downscale=2, upscale=29), scripts={"rename"})

    def test_analyse_merge(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "41/media"), files_expected_scripts=20,
                                  files_action_expected=actions(rename=0, delete=3, merge=9, upscale=8), scripts={"merge"})
        self._test_analyse_assert(join(dir_test, "41/media"),
                                  files_action_expected=actions(rename=0, delete=3, merge=6, upscale=8), scripts={"merge"})

    def test_analyse_transcode(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "45/media"),
                                  files_action_expected=actions(transcode=15), scripts={"transcode"})
        self._test_analyse_assert(join(dir_test, "45/media"),
                                  files_action_expected=actions(transcode=15, merge=15), scripts={})

    # TODO: Enable as implementation provided
    # def test_analyse_reformat(self):
    #     dir_test = self._test_prepare_dir("share_media_example", 1)
    #     self._test_analyse_assert(join(dir_test, "37/media"),
    #                               files_action_expected=actions(reformat=1), scripts={"reformat"})
    #     self._test_analyse_assert(join(dir_test, "37/media"),
    #                               files_action_expected=actions(reformat=1), scripts={"reformat"})
    #     self._test_analyse_assert(join(dir_test, "37/media"),
    #                               files_action_expected=actions(reformat=1), scripts={"reformat"})
    #
    #
    # def test_analyse_downscale(self):
    #     dir_test = self._test_prepare_dir("share_media_example", 1)
    #     self._test_analyse_assert(join(dir_test, "37/media"),
    #                               files_action_expected=actions(downscale=1), scripts={"downscale"})
    #     self._test_analyse_assert(join(dir_test, "37/media"),
    #                               files_action_expected=actions(downscale=1), scripts={"downscale"})
    #     self._test_analyse_assert(join(dir_test, "37/media"),
    #                               files_action_expected=actions(downscale=1), scripts={"downscale"})
    #

    def test_analyse_empty(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "39"),
                                  files_action_expected=actions(), scripts={}, clean=True)
        self._test_analyse_assert(join(dir_test, "33"),
                                  files_action_expected=actions(downscale=1), scripts={})
        self._test_analyse_assert(join(dir_test, "39"),
                                  files_action_expected=actions(), scripts={})

    def test_analyse_sheet(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "34"),
                                  files_action_expected=actions(rename=2, delete=1, transcode=1), clean=True, scripts={})
        self._test_analyse_assert(join(dir_test, "34/media"), scripts={})
        self._test_analyse_assert(join(dir_test, "34"), scripts={})

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
        self._test_analyse_assert(join(dir_test, "some/non-existent/path"), files_expected=-1, files_action_expected=actions())
        self._test_analyse_assert("/tmp", files_expected=-2, files_action_expected=actions())
        self._test_analyse_assert(abspath(join(dir_test, "19/tmp")), files_expected=-3, files_action_expected=actions())
        self._test_analyse_assert(join(dir_test, "10/tmp"), files_expected=-4, files_action_expected=actions())

    def _test_analyse_assert(self, dir_test, files_expected=None, files_expected_scripts=None, files_action_expected=None,
                             asserts=True, scripts=MEDIA_FILE_SCRIPTS, extensions=MEDIA_FILE_EXTENSIONS, clean=False):

        def _file_count():
            file_count = 0
            for file_root_dir, file_dirs, file_names in os.walk(dir_test):
                for file_name in file_names:
                    if splitext(file_name)[1].replace(".", "") in extensions:
                        file_count += 1
            return file_count

        sheet_guid = os.getenv("MEDIA_GOOGLE_SHEET_GUID")
        if clean:
            self.assertEqual(0, analyse._analyse("/share", sheet_guid, clean=True, verbose=True)[0])
        files_actual, files_action_actual = analyse._analyse(dir_test, sheet_guid, verbose=True)
        if asserts:
            self.assertEqual(_file_count() if files_expected is None else files_expected, files_actual)
            if files_expected is not None:
                self.assertEqual(0 if files_expected < 0 else files_expected, sum(files_action_actual.values()))
            if files_action_expected is not None:
                self.assertDictEqual(files_action_expected, files_action_actual)
        if files_actual > 0:
            for script in scripts:
                file_count = _file_count()
                for file_root_dir, file_dirs, file_names in os.walk(dir_test):
                    for file_name in file_names:
                        if file_name == "{}.sh".format(script) and \
                                not str(Path(file_root_dir).absolute()).endswith("/tmp/scripts/media"):
                            script_path = "\"{}\"".format( \
                                join(file_root_dir, file_name) \
                                    .replace("$", "\\$") \
                                    .replace("\"", "\\\""))
                            print("Running {} ...\n\n".format(script_path), flush=True)
                            time.sleep(1)
                            script_return = subprocess.run([script_path], shell=True).returncode
                            sys.stdout.flush()
                            sys.stderr.flush()
                            self.assertEqual(0, script_return)
                            print("\n\nRan {} with return code [{}]".format(script_path, script_return), flush=True)
                if asserts:
                    self.assertGreaterEqual(_file_count() if files_expected_scripts is None else files_expected_scripts, file_count)

    def test_ingress_comprehensive_1(self):
        dir_test = self._test_prepare_dir("share_tmp_example", 1)
        self._test_ingress(dir_test, 174)

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
        self.assertEqual(files_renamed, ingress._process(join(dir_test, "1/tmp"), True))
        self.assertEqual(0, ingress._process(join(dir_test, "1/tmp"), True))

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
