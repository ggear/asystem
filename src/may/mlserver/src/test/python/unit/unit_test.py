import copy
import os
import shutil
import sys
import tempfile
import unittest
from os.path import abspath, dirname, isdir, join, realpath

import pytest

sys.path.append("../../../main/python")
sys.path.append("../../../../../../rue/datascience/src/main/python")

from registry.sync import ALIAS_PREVIEW, ALIAS_RELEASE, sync
from serving.project import load_project
from workbench.demo import demo_project

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
NAME = "demo_replay_double"


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.models_dir = tempfile.mkdtemp()
        self.registry = FakeRegistry()
        self.failed = set()
        self.calls = []

    def test_a_released_model_is_served_by_name_with_its_release_label(self):
        self.registry.add(1, "1.0.0", released=True)
        self.sync()
        self.assertEqual(["1.0.0"], [settings["parameters"]["version"] for settings in self.held(NAME)])
        self.assertEqual([("load", NAME)], self.calls)
        self.assertTrue(isdir(join(self.models_dir, NAME)))

    def test_a_preview_is_served_under_its_own_name_only_while_it_differs_from_release(self):
        self.registry.add(1, "1.0.0", released=True)
        self.registry.add(2, None, previewed=True)
        self.sync()
        self.assertTrue(isdir(join(self.models_dir, NAME + "_preview")))
        self.assertTrue(self.held(NAME + "_preview")[0]["parameters"]["version"].startswith("preview-"))
        self.registry.alias(NAME, ALIAS_PREVIEW, 1)
        self.sync()
        self.assertFalse(isdir(join(self.models_dir, NAME + "_preview")))
        self.assertIn(("unload", NAME + "_preview"), self.calls)

    def test_a_model_without_the_datascience_tags_is_ignored(self):
        self.registry.add(1, "1.0.0", released=True, tagged=False)
        self.sync()
        self.assertEqual([], os.listdir(self.models_dir))

    def test_an_unchanged_registry_downloads_and_calls_nothing(self):
        self.registry.add(1, "1.0.0", released=True)
        self.sync()
        self.calls.clear()
        self.registry.downloads.clear()
        self.sync()
        self.assertEqual(([], []), (self.calls, self.registry.downloads))

    def test_the_newest_release_that_cannot_be_used_falls_back_to_the_next_most_recent(self):
        self.registry.add(1, "1.0.0")
        self.registry.add(2, "2.0.0", released=True, broken=True)
        self.sync()
        self.assertEqual(["1.0.0"], [settings["parameters"]["version"] for settings in self.held(NAME)])

    def test_a_failed_version_is_not_retried_on_every_poll(self):
        self.registry.add(1, "1.0.0")
        self.registry.add(2, "2.0.0", released=True, broken=True)
        self.sync()
        self.registry.downloads.clear()
        self.sync()
        self.assertEqual([], self.registry.downloads)

    def test_a_version_that_was_never_released_is_not_a_fallback(self):
        self.registry.add(1, None)
        self.registry.add(2, "2.0.0", released=True, broken=True)
        self.sync()
        self.assertFalse(isdir(join(self.models_dir, NAME)))

    def test_a_model_with_no_usable_version_does_not_stop_another(self):
        self.registry.add(1, "1.0.0", released=True, broken=True)
        self.registry.add(1, "1.0.0", released=True, name="demo_other")
        self.sync()
        self.assertEqual(["demo_other"], os.listdir(self.models_dir))

    def test_a_release_alias_moved_back_to_an_older_version_is_followed(self):
        self.registry.add(1, "1.0.0")
        self.registry.add(2, "2.0.0", released=True)
        self.sync()
        self.registry.alias(NAME, ALIAS_RELEASE, 1)
        self.sync()
        self.assertEqual(["1.0.0"], [settings["parameters"]["version"] for settings in self.held(NAME)])

    def test_a_refused_load_leaves_the_serving_model_untouched_and_is_not_retried(self):
        self.registry.add(1, "1.0.0", released=True)
        self.sync()
        self.registry.add(2, "2.0.0", released=True)
        self.registry.refuse = True
        self.sync()
        self.assertEqual(["1.0.0"], [settings["parameters"]["version"] for settings in self.held(NAME)])
        self.registry.downloads.clear()
        self.sync()
        self.assertEqual([], self.registry.downloads)

    def test_an_unreachable_server_still_leaves_the_files_for_it_to_load_at_start(self):
        self.registry.add(1, "1.0.0", released=True)
        sync(self.registry, self.models_dir, self.failed, lambda action, name: None)
        self.assertTrue(isdir(join(self.models_dir, NAME)))

    def test_an_unreachable_registry_leaves_every_loaded_model_serving(self):
        self.registry.add(1, "1.0.0", released=True)
        self.sync()
        self.registry.reachable = False
        self.sync()
        self.assertTrue(isdir(join(self.models_dir, NAME)))

    def test_a_model_that_loses_its_alias_is_unloaded_and_removed(self):
        self.registry.add(1, "1.0.0", released=True)
        self.sync()
        self.registry.remove_alias(NAME, ALIAS_RELEASE)
        self.sync()
        self.assertFalse(isdir(join(self.models_dir, NAME)))
        self.assertIn(("unload", NAME), self.calls)

    def sync(self):
        sync(self.registry, self.models_dir, self.failed, self.call)

    def call(self, action, name):
        self.calls.append((action, name))
        return not (self.registry.refuse and action == "load")

    def held(self, name):
        import json

        with open(join(self.models_dir, name, "model-settings.json")) as settings_file:
            return [json.load(settings_file)]


class ServingRuntimeTest(unittest.TestCase):
    def test_every_flavour_serves_what_replay_computes(self):
        from workbench.replay import replay_project

        for flavour in ("pyfunc", "wasm", "onnx"):
            project_dir = demo_project(flavour)
            self.assertEqual([], replay_project(project_dir), flavour)
            self.assertEqual({"demo_out": [3.0]}, load_project(project_dir).predict({"demo_in": [1.5]}), flavour)

    def test_a_missing_required_input_is_refused(self):
        with self.assertRaises(ValueError):
            load_project(demo_project("wasm")).predict({})

    def test_a_changed_file_is_not_loaded(self):
        project_dir = demo_project("wasm")
        with open(join(project_dir, "model.wasm"), "ab") as model_file:
            model_file.write(b"\0")
        with self.assertRaises(ValueError):
            load_project(project_dir)


class FakeRegistry:
    def __init__(self):
        self.model_list = {}
        self.projects = {}
        self.downloads = []
        self.reachable = True
        self.refuse = False

    def add(self, version, release_version, released=False, previewed=False, broken=False, tagged=True, name=NAME):
        model = self.model_list.setdefault(name, {"name": name, "aliases": {}, "versions": {}})
        project_dir = demo_project("wasm")
        if broken:
            with open(join(project_dir, "model.wasm"), "ab") as model_file:
                model_file.write(b"\0")
        tags = {"content_sha256": f"{version:064d}", "project_flavour": "wasm"} if tagged else {}
        if release_version is not None:
            tags["release_version"] = release_version
        model["versions"][str(version)] = tags
        self.projects[(name, str(version))] = project_dir
        if released:
            model["aliases"][ALIAS_RELEASE] = version
        if previewed:
            model["aliases"][ALIAS_PREVIEW] = version

    def alias(self, name, alias, version):
        self.model_list[name]["aliases"][alias] = version

    def remove_alias(self, name, alias):
        del self.model_list[name]["aliases"][alias]

    def models(self):
        if not self.reachable:
            raise OSError("registry down")
        return copy.deepcopy(list(self.model_list.values()))

    def download(self, name, version, destination):
        self.downloads.append((name, version))
        shutil.copytree(self.projects[(name, version)], join(destination, "model"))


if __name__ == "__main__":
    sys.exit(pytest.main(["-s", "-v", "--durations=50", "-o", f"cache_dir={join(DIR_ROOT, 'target/.pytest_cache')}", __file__]))
