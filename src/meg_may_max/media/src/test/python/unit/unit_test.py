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
from media import refresh
from os.path import *
from jproperties import Properties
import subprocess
import time

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

from media.analyse import MEDIA_FILE_SCRIPTS, MEDIA_FILE_EXTENSIONS


class InternetTest(unittest.TestCase):

    def test_analyse_simple(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "10/media/parents/movies/Kingdom Of Heaven (2005)"),
                                  files_action_expected=actions(
                                      reformat=1
                                  ), scripts={})

    def test_analyse_subtitles(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "22/media"),
                                  files_action_expected=actions(
                                      check=1
                                  ), scripts={})

    def test_analyse_containers(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "43/media"),
                                  files_action_expected=actions(
                                      check=2
                                  ), scripts={})

    def test_analyse_corrupt(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "32/media"),
                                  files_action_expected=actions(
                                      rename=2,
                                      check=6,
                                      reformat=5,
                                      merge=2
                                  ), scripts={})

    def test_analyse_duplicate(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "38/media"),
                                  files_action_expected=actions(
                                      rename=1,
                                      check=14,
                                      reformat=2,
                                      merge=2,
                                      nothing=3
                                  ), scripts={})

    def test_analyse_crazy_chars(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "31/media"),
                                  files_action_expected=actions(
                                      rename=12,
                                      nothing=8
                                  ), scripts={"rename"})
        self._test_analyse_assert(join(dir_test, "31/media"),
                                  files_action_expected=actions(
                                      rename=2,
                                      nothing=18
                                  ), scripts={"rename"})

    def test_analyse_ignore(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "54/media"),
                                  files_action_expected=actions(
                                      check=1,
                                      downscale=1,
                                      nothing=4
                                  ), scripts={})

    def test_analyse_rename(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "37/media"),
                                  files_action_expected=actions(
                                      rename=47,
                                      check=2,
                                      merge=3,
                                      upscale=7,
                                      nothing=4
                                  ), scripts={"rename"})
        self._test_analyse_assert(join(dir_test, "37/media"),
                                  files_action_expected=actions(
                                      rename=19,
                                      check=10,
                                      merge=3,
                                      upscale=19,
                                      reformat=10,
                                      nothing=2
                                  ), scripts={"rename"})

    def test_analyse_check(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "48/media"),
                                  files_action_expected=actions(
                                      check=3,
                                      upscale=1,
                                      reformat=1,
                                      downscale=2
                                  ))
        self._test_analyse_assert(join(dir_test, "48/media"), files_expected_scripts=10,
                                  files_action_expected=actions(
                                      check=4,
                                      merge=2,
                                      reformat=1,
                                      upscale=1,
                                      downscale=2
                                  ))
        self._test_analyse_assert(join(dir_test, "48/media"), files_expected_scripts=10,
                                  files_action_expected=actions(
                                      merge=1,
                                      upscale=1,
                                      transcode=3,
                                      reformat=1,
                                      downscale=2
                                  ), force=True)
        self._test_analyse_assert(join(dir_test, "48/media"), files_expected_scripts=12,
                                  files_action_expected=actions(
                                      check=6,
                                      merge=2,
                                      upscale=2,
                                      downscale=2
                                  ))

    def test_analyse_merge(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "41/media"),
                                  files_action_expected=actions(
                                      check=12,
                                      reformat=9,
                                      downscale=1
                                  ))
        self._test_analyse_assert(join(dir_test, "41/media"), files_expected_scripts=24,
                                  files_action_expected=actions(
                                      merge=14,
                                      reformat=9,
                                      downscale=1,
                                  ), scripts={"merge"}, force=True)
        self._test_analyse_assert(join(dir_test, "41/media"),
                                  files_action_expected=actions(
                                      check=8,
                                      upscale=4,
                                      reformat=3,
                                      downscale=1,
                                      nothing=1
                                  ), scripts={"merge"})

    def test_analyse_upscale(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "53/media"),
                                  files_action_expected=actions(
                                      check=2,
                                      upscale=1,
                                      nothing=1,
                                  ), scripts={"upscale"})
        self._test_analyse_assert(join(dir_test, "53/media"),
                                  files_action_expected=actions(
                                      check=2,
                                      upscale=1,
                                      nothing=1,
                                  ), scripts={"upscale"})

    def test_analyse_transcode(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "45/media"),
                                  files_action_expected=actions(
                                      transcode=15
                                  ), scripts={"transcode"})
        self._test_analyse_assert(join(dir_test, "45/media"),
                                  files_action_expected=actions(
                                      check=5,
                                      merge=10,
                                      transcode=15
                                  ), scripts={"transcode"})

    def test_analyse_downscale(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "46/media"),
                                  files_action_expected=actions(
                                      downscale=1
                                  ), scripts={"downscale"})
        self._test_analyse_assert(join(dir_test, "46/media"),
                                  files_action_expected=actions(
                                      merge=1,
                                      downscale=1
                                  ), scripts={"downscale"})

    def test_analyse_reformat(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "47/media"),
                                  files_action_expected=actions(
                                      reformat=3
                                  ), scripts={"reformat"})
        self._test_analyse_assert(join(dir_test, "47/media"),
                                  files_action_expected=actions(
                                      check=2,
                                      merge=1,
                                      reformat=3
                                  ), scripts={"reformat"})

    def test_analyse_profiles(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "55/media"),
                                  files_action_expected=actions(
                                      transcode=1,
                                      nothing=1
                                  ), scripts={"transcode"})
        self._test_analyse_assert(join(dir_test, "55/media"),
                                  files_action_expected=actions(
                                      merge=1,
                                      transcode=1,
                                      nothing=1
                                  ), scripts={})
        self._test_analyse_assert(join(dir_test, "55/media"), files_expected_scripts=3,
                                  files_action_expected=actions(
                                      merge=1,
                                      transcode=1,
                                      nothing=1
                                  ), scripts={"merge"})
        self._test_analyse_assert(join(dir_test, "55/media"),
                                  files_action_expected=actions(
                                      nothing=2
                                  ), scripts={})

    def test_analyse_empty(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "39"),
                                  files_action_expected=actions(
                                  ), scripts={}, clean=True)
        self._test_analyse_assert(join(dir_test, "33"),
                                  files_action_expected=actions(
                                      nothing=1
                                  ), scripts={})
        self._test_analyse_assert(join(dir_test, "39"),
                                  files_action_expected=actions(
                                  ), scripts={})

    def test_analyse_sheet(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "34"),
                                  files_action_expected=actions(
                                      rename=2,
                                      check=1,
                                      transcode=1
                                  ), clean=True, scripts={})
        self._test_analyse_assert(join(dir_test, "34/media"), scripts={})
        self._test_analyse_assert(join(dir_test, "34"), scripts={})

    def test_analyse_failures(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "some/non-existent/path"), files_expected=-1,
                                  files_action_expected=actions())
        self._test_analyse_assert("/tmp", files_expected=-2, files_action_expected=actions())
        self._test_analyse_assert(abspath(join(dir_test, "19/tmp")), files_expected=-3, files_action_expected=actions())
        self._test_analyse_assert(join(dir_test, "10/tmp"), files_expected=-4, files_action_expected=actions())

    def test_analyse_comprehensive(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "10"), asserts=False, clean=True)
        for INDEX in sorted([
            _dir.name for _dir in Path(join(DIR_ROOT, "target/runtime-unit/share_media_example_1/share")).iterdir() if
            _dir.is_dir()
        ]):
            self._test_analyse_assert(join(dir_test, INDEX), asserts=False)
            self._test_analyse_assert(join(dir_test, "{}/media".format(INDEX)), asserts=False, force=True)
            self._test_analyse_assert(join(dir_test, INDEX), asserts=False, files_expected_scripts={})
        self._test_analyse_assert(dir_test, asserts=False)

    def _test_analyse_assert(self, dir_test, files_expected=None, files_expected_scripts=None,
                             files_action_expected=None, asserts=True,
                             scripts=MEDIA_FILE_SCRIPTS, extensions=MEDIA_FILE_EXTENSIONS, clean=False, force=False,
                             defaults=False):

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
        files_actual, files_action_actual = analyse._analyse(dir_test, sheet_guid, verbose=True, force=force,
                                                             defaults=defaults)
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
                                    .replace("`", "\\`") \
                                    .replace("\"", "\\\""))
                            print("Running {} ...\n\n".format(script_path), flush=True)
                            time.sleep(1)
                            script_return = subprocess.run([script_path], shell=True).returncode
                            sys.stdout.flush()
                            sys.stderr.flush()
                            if asserts:
                                self.assertEqual(0, script_return)
                            print("\n\nRan {} with return code [{}]".format(script_path, script_return), flush=True)
                if asserts:
                    self.assertGreaterEqual(_file_count() if files_expected_scripts is None else files_expected_scripts,
                                            file_count)

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

    def test_ingress_comprehensive_5(self):
        dir_test = self._test_prepare_dir("share_tmp_example", 5)
        self._test_ingress(dir_test, 8)

    def test_ingress_comprehensive_6(self):
        dir_test = self._test_prepare_dir("share_tmp_example", 6)
        self._test_ingress(dir_test, 5)

    def _test_ingress(self, dir_test, files_renamed):
        self.assertEqual(files_renamed, ingress._process(join(dir_test, "1/tmp"), True))
        self.assertEqual(0, ingress._process(join(dir_test, "1/tmp"), True))

    def test_refresh_happy(self):
        dir_test = self._test_prepare_dir("share_media_example", 2)
        print(dir_test)
        self._test_refresh(join(dir_test, ".."), {
            "Docos Movies": [
                join(dir_test, "10/media/docos/movies"),
                join(dir_test, "20/media/docos/movies"),
                join(dir_test, "30/media/docos/movies"),
            ]
        })

    def test_refresh_sad(self):
        dir_test = self._test_prepare_dir("share_media_example", 2)
        self._test_refresh("/invalid/shares", return_value=1)
        self._test_refresh("/invalid/shares", {}, return_value=1)
        self._test_refresh("/invalid/shares", {
            "My Shows": ["/invalid/shares/1/media/my/shows", "/invalid/shares/2/media"],
            "My Movies": ["/invalid/shares/1/media/my/movies", "/invalid/shares/2/media"],
        }, return_value=1)
        self._test_refresh("/tmp", return_value=1)
        self._test_refresh("/tmp", {}, return_value=1)
        self._test_refresh("/tmp", {
            "My Shows": ["/invalid/shares/1/media/my/shows", "/invalid/shares/2/media"],
            "My Movies": ["/invalid/shares/1/media/my/movies", "/invalid/shares/2/media"],
        }, return_value=1)
        self._test_refresh(join(dir_test, ".."), {
            "Kids Movies": [join(dir_test, "10/media/kids/movies"), ]
        }, return_value=1)

    def _test_refresh(self, dir_test, library_paths={}, return_value=0):
        class MockPlexLibrarySection:
            def __init__(self, title, locations):
                self.title = title
                self.locations = locations

            def update(self):
                pass

            def analyze(self):
                pass

            def edit(self, location):
                self.locations = location

        class MockPlexLibrary:
            def __init__(self, library_paths):
                self.sections_list = [
                    MockPlexLibrarySection(title, locations)
                    for title, locations in library_paths.items()
                ]

            def sections(self):
                return self.sections_list

        class MockPlexServer:
            def __init__(self, base_url, library_paths):
                self._baseurl = base_url
                self.library = MockPlexLibrary(library_paths)

        self.assertEqual(return_value, refresh._refresh(
            MockPlexServer("http://mocked.plex.com", library_paths), dir_test))

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
