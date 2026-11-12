import contextlib
import copy
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from os.path import abspath, dirname, isdir, join, realpath

import pytest

sys.path.append("../../../main/python")
sys.path.append("../../../../../../rue/mlmodels/src/main/python")

from mlmodels.testing import example_project
from registry.sync import MlflowRegistry, sync
from serving.model.loader import ModelError, load
from serving.model.vocabulary import (
    PROJECT_ALIAS_PREVIEW,
    PROJECT_ALIAS_RELEASE,
    PROJECT_LABEL_PREVIEW,
    PROJECT_PREVIEW_SUFFIX,
    PROJECT_TAG_CONTENT_SHA256,
    PROJECT_TAG_FLAVOUR,
    PROJECT_TAG_RELEASE_VERSION,
    PROJECT_TAG_RELEASED_AT,
)

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
NAME = "demo_replay_double"


class SyncTest(unittest.TestCase):
    def setUp(self):
        self.models_dir = tempfile.mkdtemp()
        self.registry = FakeRegistry()
        self.failed = set()
        self.calls = []
        self.refuse_unload = False

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
        self.assertTrue(isdir(join(self.models_dir, NAME + PROJECT_PREVIEW_SUFFIX)))
        self.assertTrue(self.held(NAME + PROJECT_PREVIEW_SUFFIX)[0]["parameters"]["version"].startswith(PROJECT_LABEL_PREVIEW))
        self.registry.alias(NAME, PROJECT_ALIAS_PREVIEW, 1)
        self.sync()
        self.assertFalse(isdir(join(self.models_dir, NAME + PROJECT_PREVIEW_SUFFIX)))
        self.assertIn(("unload", NAME + PROJECT_PREVIEW_SUFFIX), self.calls)

    def test_a_model_without_the_mlmodels_tags_is_ignored(self):
        self.registry.add(1, "1.0.0", released=True, tagged=False)
        self.sync()
        self.assertEqual([], os.listdir(self.models_dir))

    def test_a_release_file_is_written_from_the_tags_of_a_release_and_not_of_a_preview(self):
        self.registry.add(1, "1.0.0", released=True)
        self.registry.add(2, None, previewed=True)
        self.sync()
        with open(join(self.models_dir, NAME, "release.json")) as release_file:
            release = json.load(release_file)
        self.assertEqual(("1.0.0", "2026-11-12T09:05:35Z"), (release["version"], release["released_at"]))
        self.assertFalse(os.path.isfile(join(self.models_dir, NAME + PROJECT_PREVIEW_SUFFIX, "release.json")))

    def test_a_release_whose_tags_name_another_content_is_not_served(self):
        self.registry.add(1, "1.0.0", released=True)
        self.registry.model_list[NAME]["versions"]["1"][PROJECT_TAG_CONTENT_SHA256] = "0" * 64
        self.sync()
        self.assertFalse(isdir(join(self.models_dir, NAME)))

    def test_an_unchanged_registry_downloads_and_calls_nothing(self):
        self.registry.add(1, "1.0.0", released=True)
        self.sync()
        self.calls.clear()
        self.registry.downloads.clear()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.sync()
        self.assertEqual(([], [], ""), (self.calls, self.registry.downloads, output.getvalue()))

    def test_a_change_is_reported_as_a_subject_with_a_stage_for_each_step(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.registry.add(1, "1.0.0", released=True)
            self.sync()
            self.registry.remove_alias(NAME, PROJECT_ALIAS_RELEASE)
            self.sync()
        lines = output.getvalue().splitlines()
        self.assertEqual([f"=== RUN   sync {NAME}", f"=== RUN   unload {NAME}"], [line for line in lines if line.startswith("=== RUN")])
        self.assertEqual(["download", "verify", "install", "load", "unload", "remove"], [line.split()[0] for line in lines if line.startswith("    ")])
        self.assertEqual(2, len([line for line in lines if line.startswith("--- PASS")]))

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
        self.registry.alias(NAME, PROJECT_ALIAS_RELEASE, 1)
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
        self.registry.remove_alias(NAME, PROJECT_ALIAS_RELEASE)
        self.sync()
        self.assertFalse(isdir(join(self.models_dir, NAME)))
        self.assertIn(("unload", NAME), self.calls)

    def test_a_refused_unload_keeps_the_files_for_the_next_poll(self):
        self.registry.add(1, "1.0.0", released=True)
        self.sync()
        self.registry.remove_alias(NAME, PROJECT_ALIAS_RELEASE)
        self.refuse_unload = True
        self.sync()
        self.assertTrue(isdir(join(self.models_dir, NAME)))
        self.refuse_unload = False
        self.sync()
        self.assertFalse(isdir(join(self.models_dir, NAME)))

    def sync(self):
        sync(self.registry, self.models_dir, self.failed, self.call)

    def call(self, action, name):
        self.calls.append((action, name))
        return not ((self.registry.refuse and action == "load") or (self.refuse_unload and action == "unload"))

    def held(self, name):
        import json

        with open(join(self.models_dir, name, "model-settings.json")) as settings_file:
            return [json.load(settings_file)]


class MlflowRegistryTest(unittest.TestCase):
    def test_every_model_and_version_is_read_beyond_one_page(self):
        directory = tempfile.mkdtemp()
        registry = MlflowRegistry(f"sqlite:///{directory}/mlflow.db")
        for number in range(101):
            registry.client.create_registered_model(f"demo_{number:03d}")
            registry.client.create_model_version(f"demo_{number:03d}", "file:///nowhere", tags={PROJECT_TAG_CONTENT_SHA256: str(number)})
        models = registry.models()
        self.assertEqual(101, len(models))
        self.assertEqual({"1": {PROJECT_TAG_CONTENT_SHA256: "100"}}, next(model for model in models if model["name"] == "demo_100")["versions"])


class ServingRuntimeTest(unittest.TestCase):
    def test_every_flavour_serves_what_replay_computes(self):
        from mlmodels._replay import replay_project

        for example in ("static/constant", "wasm/accumulate", "wasm/saturate", "onnx/linear", "pyfunc/linear"):
            project_dir = example_project(example)
            self.assertEqual([], replay_project(project_dir), example)
            with open(join(project_dir, "golden.json")) as golden_file:
                step = next(step for sequence in json.load(golden_file)["sequences"] for step in sequence["steps"] if "response" in step)
            served = load(project_dir).predict({entry["name"]: entry["data"] for entry in step["request"]["inputs"]})
            expected = {entry["name"]: entry["data"] for entry in step["response"]["outputs"]}
            self.assertEqual(expected.keys(), served.keys(), example)
            for name, values in expected.items():
                for value, actual in zip(values, served[name], strict=True):
                    self.assertAlmostEqual(value, actual, places=9, msg=f"{example} {name}")

    def test_a_missing_required_input_is_refused(self):
        with self.assertRaises(ModelError):
            load(example_project("wasm/accumulate")).predict({})

    def test_a_changed_file_is_not_loaded(self):
        project_dir = example_project("wasm/accumulate")
        with open(join(project_dir, "model.wasm"), "ab") as model_file:
            model_file.write(b"\0")
        with self.assertRaises(ModelError):
            load(project_dir)


class FakeRegistry:
    def __init__(self):
        self.model_list = {}
        self.projects = {}
        self.downloads = []
        self.reachable = True
        self.refuse = False

    def add(self, version, release_version, released=False, previewed=False, broken=False, tagged=True, name=NAME):
        model = self.model_list.setdefault(name, {"name": name, "aliases": {}, "versions": {}})
        project_dir = example_project("wasm/accumulate")
        if broken:
            with open(join(project_dir, "model.wasm"), "ab") as model_file:
                model_file.write(b"\0")
        with open(join(project_dir, "project.json"), "rb") as manifest_file:
            actual = hashlib.sha256(manifest_file.read()).hexdigest()
        tags = {PROJECT_TAG_CONTENT_SHA256: actual, PROJECT_TAG_FLAVOUR: "wasm"} if tagged else {}
        if release_version is not None:
            tags[PROJECT_TAG_RELEASE_VERSION] = release_version
            tags[PROJECT_TAG_RELEASED_AT] = "2026-11-12T09:05:35Z"
        model["versions"][str(version)] = tags
        self.projects[(name, str(version))] = project_dir
        if released:
            model["aliases"][PROJECT_ALIAS_RELEASE] = version
        if previewed:
            model["aliases"][PROJECT_ALIAS_PREVIEW] = version

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
