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
                                      reformat=4,
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

    def test_analyse_missing_profile(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "57/media"),
                                  files_action_expected=actions(
                                      check=2,
                                      nothing=1
                                  ), scripts={})

    def test_analyse_profiles(self):
        dir_test = self._test_prepare_dir("share_media_example", 1)
        self._test_analyse_assert(join(dir_test, "56/media"),
                                  files_action_expected=actions(
                                      merge=5,
                                      upscale=1,
                                      transcode=9,
                                      reformat=1,
                                      downscale=2,
                                      nothing=3
                                  ), scripts={"transcode", "reformat", "downscale"})
        self._test_analyse_assert(join(dir_test, "56/media"),
                                  files_action_expected=actions(
                                      merge=16,
                                      upscale=1,
                                      transcode=9,
                                      reformat=1,
                                      downscale=2,
                                      nothing=3
                                  ), scripts={})
        self._test_analyse_assert(join(dir_test, "56/media"), files_expected_scripts=35,
                                  files_action_expected=actions(
                                      merge=16,
                                      upscale=1,
                                      transcode=9,
                                      reformat=1,
                                      downscale=2,
                                      nothing=3
                                  ), scripts={"merge"})
        self._test_analyse_assert(join(dir_test, "56/media"),
                                  files_action_expected=actions(
                                      merge=8,
                                      upscale=1,
                                      transcode=4,
                                      nothing=11
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
                            time.sleep(0.1)
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
        self._test_refresh(dir_test, {
            "Docos Movies": [
                "/share/10/media/docos/movies",
                "/share/20/media/docos/movies",
                "/share/30/media/docos/movies",
            ]
        }, locations_expected={
            "Docos Movies": [
                "/share/10/media/docos/movies",
                "/share/20/media/docos/movies",
                "/share/30/media/docos/movies",
            ]
        })
        self._test_refresh(dir_test, {
            "Docos Movies": [
                "/share/20/media/docos/movies",
            ]
        }, locations_expected={
            "Docos Movies": [
                "/share/10/media/docos/movies",
                "/share/20/media/docos/movies",
            ]
        })

    def test_refresh_sad(self):
        dir_test = self._test_prepare_dir("share_media_example", 2)
        self._test_refresh("/invalid/shares", return_value=refresh.Exit.FAIL_FILESYSTEM)
        self._test_refresh("/invalid/shares", {}, return_value=refresh.Exit.FAIL_FILESYSTEM)
        self._test_refresh("/invalid/shares", {
            "My Shows": ["/invalid/shares/1/media/my/shows", "/invalid/shares/2/media"],
            "My Movies": ["/invalid/shares/1/media/my/movies", "/invalid/shares/2/media"],
        }, return_value=refresh.Exit.FAIL_FILESYSTEM)
        self._test_refresh("/tmp", return_value=refresh.Exit.FAIL_FILESYSTEM)
        self._test_refresh("/tmp", {}, return_value=refresh.Exit.FAIL_FILESYSTEM)
        self._test_refresh("/tmp", {
            "My Shows": ["/invalid/shares/1/media/my/shows", "/invalid/shares/2/media"],
            "My Movies": ["/invalid/shares/1/media/my/movies", "/invalid/shares/2/media"],
        }, return_value=refresh.Exit.FAIL_FILESYSTEM)
        self._test_refresh(dir_test, {
            "Kids Movies": ["/share/10/media/kids/movies", ]
        }, return_value=refresh.Exit.FAIL_PLEX_LIBRARY)

    def test_refresh_sabnzbd(self):
        dir_test = self._test_prepare_dir("share_media_example", 2)
        library_paths = {
            "Docos Movies": [
                "/share/10/media/docos/movies",
                "/share/20/media/docos/movies",
                "/share/30/media/docos/movies",
            ]
        }
        completed_slot = {"status": "Completed", "name": "Some.Movie.2026", "fail_message": ""}
        failed_slot = {"status": "Failed", "name": "Broken.Movie.2026", "fail_message": "Unpack failed"}
        running_slot = {"status": "Extracting", "name": "Busy.Movie.2026", "fail_message": ""}

        def archives(_sabnzbd):
            return [call for call in _sabnzbd.calls if call.get("name") == "delete"]

        sabnzbd = self._test_refresh(dir_test, library_paths, history_slots=[])
        self.assertEqual([], archives(sabnzbd))
        self.assertEqual({"mode": "history", "limit": 1, "status": "Completed"}, sabnzbd.calls[0])

        sabnzbd = self._test_refresh(dir_test, library_paths, history_slots=[completed_slot])
        self.assertEqual([{"mode": "history", "name": "delete", "value": "completed", "archive": 1}], archives(sabnzbd))

        sabnzbd = self._test_refresh(dir_test, library_paths, history_slots=[running_slot])
        self.assertEqual([], archives(sabnzbd))

        sabnzbd = self._test_refresh(dir_test, library_paths, history_slots=[failed_slot],
                                     return_value=refresh.Exit.FAIL_SABNZBD_DOWNLOAD)
        self.assertEqual(["failed"], [call["value"] for call in archives(sabnzbd)])

        sabnzbd = self._test_refresh(dir_test, library_paths, history_slots=[completed_slot, failed_slot],
                                     return_value=refresh.Exit.FAIL_SABNZBD_DOWNLOAD)
        self.assertEqual(["completed", "failed"], [call["value"] for call in archives(sabnzbd)])

        sabnzbd = self._test_refresh(dir_test, library_paths, history_slots=[failed_slot] * 250,
                                     return_value=refresh.Exit.FAIL_SABNZBD_DOWNLOAD)
        self.assertEqual(["failed"], [call["value"] for call in archives(sabnzbd)])
        self.assertEqual([0, 100, 200], [call["start"] for call in sabnzbd.calls if "start" in call])

        self._test_refresh(dir_test, library_paths, connect_error=True,
                           return_value=refresh.Exit.FAIL_SABNZBD_CONNECT)

        self._test_refresh(dir_test, library_paths, history_slots=[completed_slot], archive_error=True,
                           return_value=refresh.Exit.FAIL_SABNZBD_ARCHIVE)

    def test_refresh_sonarr(self):
        dir_test = self._test_prepare_dir("share_media_example", 2)
        library_paths = {
            "Docos Movies": [
                "/share/10/media/docos/movies",
                "/share/20/media/docos/movies",
                "/share/30/media/docos/movies",
            ]
        }
        def resources(monitored=True):
            return {"series": [{"id": 7, "title": "Ted Lasso", "monitored": monitored}]}

        sonarr = self._test_refresh(dir_test, library_paths, sonarr_resources=resources())
        self.assertEqual([], sonarr.puts)
        self.assertEqual([
            ("command", {"name": "RefreshMonitoredDownloads"}),
            ("command", {"name": "RescanSeries", "seriesId": 7}),
            ("command", {"name": "RefreshSeries", "seriesId": 7}),
        ], sonarr.posts)

        sonarr = self._test_refresh(dir_test, library_paths, sonarr_resources={"series": []})
        self.assertEqual([], sonarr.puts)
        self.assertEqual([
            ("command", {"name": "RefreshMonitoredDownloads"}),
        ], sonarr.posts)

        sonarr = self._test_refresh(dir_test, library_paths, sonarr_resources=resources(False))
        self.assertEqual(["series/7"], [resource for resource, _ in sonarr.puts])
        self.assertEqual(True, sonarr.puts[0][1]["monitored"])

        self._test_refresh(dir_test, library_paths, sonarr_resources=resources(), sonarr_error="series",
                           return_value=refresh.Exit.FAIL_SONARR_CONNECT)
        self._test_refresh(dir_test, library_paths, sonarr_resources=resources(False), sonarr_error="series/7",
                           return_value=refresh.Exit.FAIL_SONARR_CONFIGURE)
        self._test_refresh(dir_test, library_paths, sonarr_resources=resources(),
                           sonarr_error="RefreshMonitoredDownloads",
                           return_value=refresh.Exit.FAIL_SONARR_ACTIVITY)
        self._test_refresh(dir_test, library_paths, sonarr_resources=resources(), sonarr_error="RescanSeries",
                           return_value=refresh.Exit.FAIL_SONARR_REFRESH)

    def test_refresh_sonarr_series_state(self):
        dir_test = self._test_prepare_dir("share_media_example", 2)
        library_paths = {
            "Docos Movies": [
                "/share/10/media/docos/movies",
                "/share/20/media/docos/movies",
                "/share/30/media/docos/movies",
            ]
        }

        def series(_ended, _episodes, _files):
            return {"id": 7, "title": "Ted Lasso", "monitored": True, "ended": _ended,
                    "statistics": {"episodeCount": _episodes, "episodeFileCount": _files,
                                   "percentOfEpisodes": _files * 100 // _episodes}}

        self._test_refresh(dir_test, library_paths,
                           sonarr_resources={"series": [series(False, 10, 10)], "queue": []})

        self._test_refresh(dir_test, library_paths,
                           sonarr_resources={"series": [series(True, 10, 10)], "queue": []})

        self._test_refresh(dir_test, library_paths,
                           sonarr_resources={"series": [series(False, 10, 8)], "queue": []},
                           return_value=refresh.Exit.FAIL_SONARR_MISSING)

        self._test_refresh(dir_test, library_paths,
                           sonarr_resources={"series": [series(False, 10, 8)], "queue": [{"seriesId": 7}]})

        sonarr = self._test_refresh(dir_test, library_paths, sonarr_command_status="queued",
                                    sonarr_resources={"series": [series(False, 10, 10)], "queue": []})
        self.assertEqual(3, len([resource for resource, _ in sonarr.posts if resource == "command"]))

        self._test_refresh(dir_test, library_paths, sonarr_command_status="failed",
                           sonarr_resources={"series": [series(False, 10, 10)], "queue": []},
                           return_value=refresh.Exit.FAIL_SONARR_ACTIVITY)

    def test_refresh_sonarr_defaults(self):
        dir_test = self._test_prepare_dir("share_media_example", 2)
        library_paths = {
            "Docos Movies": [
                "/share/10/media/docos/movies",
                "/share/20/media/docos/movies",
                "/share/30/media/docos/movies",
            ]
        }

        def resources(_seasons, _profile_id=4):
            return {
                "series": [{"id": 7, "title": "Ted Lasso", "monitored": True, "qualityProfileId": _profile_id,
                            "seasons": _seasons}],
                "qualityProfile": [{"id": 4, "name": "HD-1080p"}, {"id": 1, "name": "Any"}],
                "queue": [],
            }

        sonarr = self._test_refresh(dir_test, library_paths, sonarr_resources=resources(
            [{"seasonNumber": 0, "monitored": False}, {"seasonNumber": 1, "monitored": True}]))
        self.assertEqual([], sonarr.puts)

        sonarr = self._test_refresh(dir_test, library_paths, sonarr_resources=resources(
            [{"seasonNumber": 0, "monitored": False}, {"seasonNumber": 1, "monitored": False}]))
        self.assertEqual(["series/7"], [resource for resource, _ in sonarr.puts])
        self.assertEqual([{"seasonNumber": 0, "monitored": False}, {"seasonNumber": 1, "monitored": True}],
                         sonarr.puts[0][1]["seasons"])

        sonarr = self._test_refresh(dir_test, library_paths, sonarr_resources=resources(
            [{"seasonNumber": 1, "monitored": True}], _profile_id=1))
        self.assertEqual(["series/7"], [resource for resource, _ in sonarr.puts])
        self.assertEqual(4, sonarr.puts[0][1]["qualityProfileId"])

    def test_refresh_plex_matches(self):
        dir_test = self._test_prepare_dir("share_media_example", 2)
        library_paths = {
            "Docos Movies": [
                "/share/10/media/docos/movies",
                "/share/20/media/docos/movies",
                "/share/30/media/docos/movies",
            ]
        }
        self._test_refresh(dir_test, library_paths, plex_items=[("Some Film (2019)", "plex://movie/abc")])
        self._test_refresh(dir_test, library_paths, plex_items=[("Some Film (2019)", "local://12345")])

    def test_refresh_sabnzbd_queue(self):
        dir_test = self._test_prepare_dir("share_media_example", 2)
        library_paths = {
            "Docos Movies": [
                "/share/10/media/docos/movies",
                "/share/20/media/docos/movies",
                "/share/30/media/docos/movies",
            ]
        }
        sabnzbd = self._test_refresh(dir_test, library_paths, queue_slots=[
            {"filename": "Rose.of.Nevada.2025", "status": "Downloading", "percentage": "35", "timeleft": "0:46:09"},
        ])
        self.assertEqual({"mode": "queue"}, sabnzbd.calls[-1])

    def _test_refresh(self, dir_test, library_paths=None, return_value=0, locations_expected=None,
                      history_slots=None, queue_slots=None, connect_error=False, archive_error=False,
                      sonarr_resources=None, sonarr_error=None, sonarr_command_status="completed",
                      plex_items=None):
        library_paths = {} if library_paths is None else library_paths

        class MockSabnzbdResponse:
            def __init__(self, payload):
                self.payload = payload

            def raise_for_status(self):
                pass

            def json(self):
                return self.payload

        class MockRequests:
            def __init__(self, slots, resources):
                self.slots = [] if slots is None else slots
                self.resources = {} if resources is None else resources
                self.queue = [] if queue_slots is None else queue_slots
                self.calls = []
                self.posts = []
                self.puts = []

            def _sonarr(self, _url, _payload=None):
                resource = _url.rsplit("/api/v3/", 1)[1]
                resource = resource.split("?", 1)[0]
                if sonarr_error is not None and sonarr_error in (resource, (_payload or {}).get("name")):
                    raise Exception(f"mocked sonarr [{sonarr_error}] failure")
                if _payload is not None:
                    return MockSabnzbdResponse({"id": 1, "status": sonarr_command_status, "result": "successful"})
                if resource.startswith("command/"):
                    return MockSabnzbdResponse({"id": 1, "status": "completed", "result": "successful"})
                if resource.startswith("series/"):
                    series_id = int(resource.split("/", 1)[1])
                    return MockSabnzbdResponse(
                        next(item for item in self.resources.get("series", []) if item["id"] == series_id))
                if resource == "queue":
                    records = self.resources.get("queue", [])
                    return MockSabnzbdResponse({"records": records, "totalRecords": len(records)})
                return MockSabnzbdResponse(self.resources.get(resource, []))

            def post(self, _url, timeout=None, headers=None, json=None):
                self.posts.append((_url.rsplit("/api/v3/", 1)[1].split("?", 1)[0], json))
                return self._sonarr(_url, json)

            def put(self, _url, timeout=None, headers=None, json=None):
                self.puts.append((_url.rsplit("/api/v3/", 1)[1].split("?", 1)[0], json))
                return self._sonarr(_url, json)

            def get(self, _url, timeout=None, params=None, headers=None):
                if "/api/v3/" in _url:
                    return self._sonarr(_url)
                parameters = {key: value for key, value in params.items() if key not in ("output", "apikey")}
                self.calls.append(parameters)
                if parameters.get("name") == "delete":
                    if archive_error:
                        raise Exception("mocked sabnzbd archive failure")
                    return MockSabnzbdResponse({"status": True})
                if connect_error:
                    raise Exception("mocked sabnzbd connect failure")
                if parameters.get("mode") == "queue":
                    return MockSabnzbdResponse({"queue": {"slots": self.queue}})
                slots = self.slots
                if parameters.get("failed_only"):
                    slots = [slot for slot in slots if slot["status"] == "Failed"]
                if parameters.get("status"):
                    slots = [slot for slot in slots if slot["status"] == parameters["status"]]
                start = parameters.get("start", 0)
                limit = parameters.get("limit", len(slots))
                return MockSabnzbdResponse({"history": {"noofslots": len(slots), "slots": slots[start:start + limit]}})

        class MockPlexItem:
            def __init__(self, title, guid):
                self.title = title
                self.guid = guid

        class MockPlexLibrarySection:
            def __init__(self, title, locations):
                self.title = title
                self.locations = locations
                self.items = [MockPlexItem(title, guid) for title, guid in (plex_items or [])]

            def search(self, filters=None):
                return self.items

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
                self.activities = []

        plex_server = MockPlexServer("http://mocked.plex.com", library_paths)
        sabnzbd = MockRequests(history_slots, sonarr_resources)
        plex_server_class = refresh.PlexServer
        requests_module = refresh.requests
        settle_seconds = refresh.PLEX_SETTLE_SECONDS
        settle_poll_seconds = refresh.PLEX_SETTLE_POLL_SECONDS
        refresh.PlexServer = lambda _plex_url, _plex_token, **_parameters: plex_server
        refresh.requests = sabnzbd
        refresh.PLEX_SETTLE_SECONDS = 0
        refresh.PLEX_SETTLE_POLL_SECONDS = 0
        try:
            self.assertEqual(return_value, refresh._refresh(dir_test))
        finally:
            refresh.PlexServer = plex_server_class
            refresh.requests = requests_module
            refresh.PLEX_SETTLE_SECONDS = settle_seconds
            refresh.PLEX_SETTLE_POLL_SECONDS = settle_poll_seconds
        if locations_expected is not None:
            self.assertEqual(locations_expected, {
                section.title: sorted(section.locations) for section in plex_server.library.sections()})
        return sabnzbd

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
    sys.exit(pytest.main(["-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache", __file__, ]))
