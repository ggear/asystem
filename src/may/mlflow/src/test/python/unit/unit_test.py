import os
import sys
import tempfile
import unittest
from os.path import abspath, dirname, join, realpath
from unittest import mock

import pytest

sys.path.append("../../../main/python")

import library.data
from library.env import init_env

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))


class WrangleTest(unittest.TestCase):
    def test_init_env(self):
        self.assertEqual("/service/mlflow/artifacts", init_env()["MLFLOW_ARTIFACT_DIR"])


class QueryInfluxdb3Test(unittest.TestCase):
    def setUp(self):
        self.data_dir = tempfile.mkdtemp()
        self.env = {"INFLUXDB3_IP_PROD": "host", "INFLUXDB3_API_PORT": "1", "INFLUXDB3_TOKEN_ADMIN": "token", "INFLUXDB3_DATABASE_HOME": "home"}

    def response(self, text, ok=True):
        return mock.Mock(ok=ok, status_code=200 if ok else 400, text=text)

    def query(self, post, **kwargs):
        with mock.patch.object(library.data, "post", post):
            return library.data.query_influxdb3(self.env, "SELECT 1", "demo_model", "training", "demo", model_dir=self.data_dir, **kwargs)

    def test_writes_csv_when_absent_then_reads_it(self):
        post = mock.Mock(return_value=self.response("time,value\n2026-01-01T00:00:00,1.5\n"))
        first = self.query(post)
        second = self.query(post)
        self.assertEqual(first, second)
        self.assertEqual(1, post.call_count)
        self.assertEqual("1.5", first[0][1])

    def test_force_overrides_the_present_file(self):
        self.query(mock.Mock(return_value=self.response("time,value\n2026-01-01T00:00:00,1.5\n")))
        rows = self.query(mock.Mock(return_value=self.response("time,value\n2026-01-01T00:00:00,2.5\n")), force=True)
        self.assertEqual("2.5", rows[0][1])
        path = library.data.data_path("demo_model", "training", "demo", model_dir=self.data_dir)
        with open(path) as data_file:
            self.assertIn("2.5", data_file.read())
        self.assertEqual(1, len(os.listdir(os.path.join(self.data_dir, "demo_model", "data", "training"))))

    def test_shared_timestamp_dir(self):
        post = mock.Mock(return_value=self.response("time,value\n"))
        self.query(post, timestamp="2026-01-01_00-00-00")
        self.assertTrue(os.path.isfile(os.path.join(self.data_dir, "demo_model", "data", "training", "2026-01-01_00-00-00", "demo.csv")))

    def test_unknown_label_fails(self):
        with self.assertRaises(ValueError):
            library.data.data_path("demo_model", "testing", "demo", model_dir=self.data_dir)

    def test_failed_query_writes_nothing(self):
        with self.assertRaises(RuntimeError):
            self.query(mock.Mock(return_value=self.response("bad", ok=False)))
        self.assertFalse(os.path.isdir(os.path.join(self.data_dir, "demo_model", "data", "training")))


if __name__ == "__main__":
    sys.exit(
        pytest.main(
            [
                "-s",
                "-v",
                "--durations=50",
                "-o",
                f"cache_dir={join(DIR_ROOT, 'target/.pytest_cache')}",
                __file__,
            ]
        )
    )


class ConsumerProjectDirTest(unittest.TestCase):
    def test_slot_resolves_into_the_tree_or_the_output_directory(self):
        from library.project import consumer_project_dir

        self.assertTrue(consumer_project_dir("max/rackmains", "default").endswith("max/rackmains/src/build/resources/model/default"))
        with mock.patch.dict(os.environ, {"MODEL_OUTPUT_DIR": "/out"}):
            self.assertEqual("/out/max/rackmains/default", consumer_project_dir("max/rackmains", "default"))
        with self.assertRaises(ValueError):
            consumer_project_dir("max/rackmains", "other")


class DevelopmentVersionTest(unittest.TestCase):
    def test_the_workspace_version_file_is_read(self):
        from library.project import development_version

        model_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(model_dir, "demo/calc/run"))
        with open(os.path.join(model_dir, "demo/calc/run/.version"), "w") as version_file:
            version_file.write("1003-SNAPSHOT\n")
        self.assertEqual("1003-SNAPSHOT", development_version("demo/calc/run", model_dir))


class ScratchProjectDirTest(unittest.TestCase):
    def test_a_run_without_an_output_directory_gets_a_temporary_project(self):
        from library.project import scratch_project_dir

        with mock.patch.dict(os.environ, {"MODEL_OUTPUT_DIR": ""}):
            self.assertTrue(scratch_project_dir("demo/calc/run").endswith("/project"))

    def test_a_run_with_an_output_directory_gets_a_fresh_project_under_it(self):
        from library.project import scratch_project_dir

        output_dir = tempfile.mkdtemp()
        stale = join(output_dir, "project", "demo/calc/run")
        os.makedirs(stale)
        open(join(stale, "old.json"), "w").close()
        self.assertEqual(stale, scratch_project_dir("demo/calc/run", output_dir))
        self.assertFalse(os.path.exists(stale))


class EnsureDataTest(unittest.TestCase):
    def test_a_dataset_is_built_once_and_then_read(self):
        from library.data import ensure_data

        model_dir = tempfile.mkdtemp()
        builds = []

        def build():
            builds.append(1)
            return {"x": [1.0, 2.0]}

        first, path = ensure_data("demo/calc/run", "training", "demo_training", build, "2026-11-03_10-00-00", model_dir)
        second, _ = ensure_data("demo/calc/run", "training", "demo_training", build, "2026-11-03_10-00-00", model_dir)
        self.assertEqual(1, len(builds))
        self.assertEqual(first.to_dicts(), second.to_dicts())
        self.assertTrue(os.path.isfile(path))

    def test_an_absent_dataset_without_a_builder_is_an_error(self):
        from library.data import ensure_data

        with self.assertRaises(FileNotFoundError):
            ensure_data("demo/calc/run", "backtest", "demo_backtest", None, "2026-11-03_10-00-00", tempfile.mkdtemp())


class ReplayRunnerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import subprocess

        build = subprocess.run([join(DIR_ROOT, "src/main/resources/model.sh"), "build"], capture_output=True, text=True, timeout=900, check=False)
        cls.runners = {"rust": join(DIR_ROOT, "target/rust/debug/modelreplay"), "go": join(DIR_ROOT, "target/go/modelreplay")}
        if build.returncode != 0 or not all(os.path.isfile(path) for path in cls.runners.values()):
            raise unittest.SkipTest(f"the Rust and Go runners could not be built [{build.stderr.strip()[-200:]}]")

    def project(self, flavor):
        import wasmtime

        from asystem.model import build_signature, evaluate_acceptance, package_project, signature_input, signature_output, stamp_model

        work_dir = tempfile.mkdtemp()
        model_path = None
        constants = None
        if flavor == "wasm":
            model_path = join(work_dir, "model.wasm")
            wat = '(module (memory (export "memory") 1) (func (export "predict") (param i32 i32 i32) (f64.store (local.get 2) (f64.mul (f64.load (local.get 0)) (f64.const 2)))))'
            with open(model_path, "wb") as model_file:
                model_file.write(wasmtime.wat2wasm(wat))
            stamp_model(model_path, "wasm", "1")
        elif flavor == "pyfunc":
            model_path = join(work_dir, "model.py")
            with open(model_path, "w") as model_file:
                model_file.write(
                    'import pandas as pd\nfrom mlflow.models import set_model\nfrom mlflow.pyfunc import PythonModel\n\nMODEL_VERSION = "1"\n\n\n'
                    'class Double(PythonModel):\n    def predict(self, context, model_input, params=None):\n        return pd.DataFrame({"demo_out": [x * 2.0 for x in model_input["demo_in"]]})\n\n\nset_model(Double())\n'
                )
        else:
            constants = {"demo_out": 4.0}
        version = "static-1" if flavor == "static" else "1"
        signature = build_signature("demo_replay_double", [version], [signature_input("demo_in", "none", "A number.")], [signature_output("demo_out", "none", "Twice the number.", datatype="FP64")])
        dataset = join(work_dir, "2026-11-03_10-00-00", "demo_replay_backtest_2026-11-01_2026-11-02.csv")
        os.makedirs(dirname(dataset))
        with open(dataset, "w") as dataset_file:
            dataset_file.write("a,b\n1,2\n")
        evaluation = None
        if flavor != "static":
            evaluation = evaluate_acceptance(lambda: [{"split": "backtest", "output": "demo_out", "name": "rmse", "value": 0.0, "limit": 1, "direction": "max"}], {"backtest": [dataset]})
        first = 4.0 if constants else 3.0
        samples = [{"demo_in": 1.5, "demo_out": first}, {"demo_in": 2.0, "demo_out": 4.0}, {"demo_in": None, "expect": "error"}]
        project_dir = join(work_dir, "project")
        package_project(
            project_dir,
            "demo_replay_double",
            version,
            flavor,
            signature,
            samples,
            {"source": "manual", "inputs": [], "implementation": "demo built by hand"},
            constants=constants,
            model_path=model_path,
            evaluation=evaluation,
        )
        return project_dir

    def run_runner(self, host, project_dir):
        import subprocess

        return subprocess.run([self.runners[host], project_dir], capture_output=True, text=True, timeout=120, check=False)

    def retouch(self, project_dir, change):
        import json

        from asystem.model import file_sha256

        golden_path = join(project_dir, "golden.json")
        with open(golden_path) as golden_file:
            golden = json.load(golden_file)
        change(golden)
        with open(golden_path, "w") as golden_file:
            json.dump(golden, golden_file)
        manifest_path = join(project_dir, "project.json")
        with open(manifest_path) as manifest_file:
            manifest = json.load(manifest_file)
        manifest["files"]["golden"]["sha256"] = file_sha256(golden_path)
        with open(manifest_path, "w") as manifest_file:
            json.dump(manifest, manifest_file)

    def test_each_runner_replays_a_static_and_a_wasm_project(self):
        for flavor in ("static", "wasm"):
            project_dir = self.project(flavor)
            for host in self.runners:
                completed = self.run_runner(host, project_dir)
                self.assertEqual(0, completed.returncode, f"{host} {flavor} {completed.stderr}")
                self.assertIn(f'"host":"{host}"', completed.stdout.replace(" ", ""))
                self.assertIn('"passed":true', completed.stdout.replace(" ", ""))

    def test_each_runner_skips_a_flavor_it_does_not_support(self):
        project_dir = self.project("pyfunc")
        for host in self.runners:
            self.assertEqual(2, self.run_runner(host, project_dir).returncode, host)

    def test_each_runner_rejects_a_response_that_differs_from_the_golden(self):
        for flavor in ("static", "wasm"):
            project_dir = self.project(flavor)
            self.retouch(project_dir, lambda golden: golden["sequences"][0]["steps"][0]["response"]["outputs"][0]["data"].__setitem__(0, 99.0))
            for host in self.runners:
                completed = self.run_runner(host, project_dir)
                self.assertEqual(1, completed.returncode, f"{host} {flavor}")
                self.assertIn("RP003", completed.stderr)

    def test_each_runner_applies_a_stated_tolerance(self):
        def tolerate(shift):
            def change(golden):
                golden["tolerance"] = {"demo_out": {"absolute": 1e-3}}
                golden["sequences"][0]["steps"][1]["response"]["outputs"][0]["data"][0] += shift

            return change

        for flavor in ("static", "wasm"):
            near, far = self.project(flavor), self.project(flavor)
            self.retouch(near, tolerate(1e-6))
            self.retouch(far, tolerate(0.5))
            for host in self.runners:
                self.assertEqual(0, self.run_runner(host, near).returncode, f"{host} {flavor}")
                self.assertEqual(1, self.run_runner(host, far).returncode, f"{host} {flavor}")

    def test_each_runner_rejects_a_file_that_differs_from_its_manifest_hash(self):
        project_dir = self.project("wasm")
        with open(join(project_dir, "golden.json"), "a") as golden_file:
            golden_file.write(" ")
        for host in self.runners:
            completed = self.run_runner(host, project_dir)
            self.assertEqual(1, completed.returncode, host)
            self.assertIn("PJ003", completed.stderr)

    def test_the_gate_collects_a_row_per_runtime_and_names_the_skipped_ones(self):
        from asystem.replay import gate_project

        runners = {host: [path] for host, path in self.runners.items()}
        document, findings = gate_project(self.project("wasm"), runners)
        self.assertEqual([], findings)
        self.assertEqual(["python", "rust", "go"], [row["host"] for row in document["results"]])
        self.assertEqual([], document["skipped"])
        document, findings = gate_project(self.project("pyfunc"), runners)
        self.assertEqual(["rust", "go"], document["skipped"])
