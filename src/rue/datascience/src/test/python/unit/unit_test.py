import os
import sys
import tempfile
import unittest
from os.path import abspath, dirname, join, realpath
from unittest import mock

sys.path.append("../../../main/python")

import workbench.data
from asystem.report import run_pytest
from workbench.env import init_env

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))


class WrangleTest(unittest.TestCase):
    def test_init_env(self):
        self.assertTrue(init_env()["MLFLOW_TRACKING_URI"].startswith("http"))


class QueryInfluxdb3Test(unittest.TestCase):
    def setUp(self):
        self.data_dir = tempfile.mkdtemp()
        self.env = {"INFLUXDB3_IP_PROD": "host", "INFLUXDB3_API_PORT": "1", "INFLUXDB3_TOKEN_ADMIN": "token", "INFLUXDB3_DATABASE_HOME": "home"}

    def response(self, text, ok=True):
        return mock.Mock(ok=ok, status_code=200 if ok else 400, text=text)

    def query(self, post, **kwargs):
        with mock.patch.object(workbench.data, "post", post):
            return workbench.data.query_influxdb3(self.env, "SELECT 1", "demo_model", "training", "demo", notebook_dir=self.data_dir, **kwargs)

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
        path = workbench.data.data_path("demo_model", "training", "demo", notebook_dir=self.data_dir)
        with open(path) as data_file:
            self.assertIn("2.5", data_file.read())
        self.assertEqual(1, len(os.listdir(os.path.join(self.data_dir, "demo_model", "data", "training"))))

    def test_shared_timestamp_dir(self):
        post = mock.Mock(return_value=self.response("time,value\n"))
        self.query(post, timestamp="2026-01-01_00-00-00")
        self.assertTrue(os.path.isfile(os.path.join(self.data_dir, "demo_model", "data", "training", "2026-01-01_00-00-00", "demo.csv")))

    def test_unknown_label_fails(self):
        with self.assertRaises(ValueError):
            workbench.data.data_path("demo_model", "testing", "demo", notebook_dir=self.data_dir)

    def test_failed_query_writes_nothing(self):
        with self.assertRaises(RuntimeError):
            self.query(mock.Mock(return_value=self.response("bad", ok=False)))
        self.assertFalse(os.path.isdir(os.path.join(self.data_dir, "demo_model", "data", "training")))


class BuildWasmTest(unittest.TestCase):
    def run_module(self, module_bytes, rows, outputs):
        import struct

        import wasmtime

        engine = wasmtime.Engine()
        store = wasmtime.Store(engine)
        instance = wasmtime.Instance(store, wasmtime.Module(engine, module_bytes), [])
        exports = instance.exports(store)
        memory = exports["memory"]
        function = exports["predict"]
        assert isinstance(memory, wasmtime.Memory) and isinstance(function, wasmtime.Func)
        flat = [value for row in rows for value in row]
        memory.write(store, struct.pack(f"<{len(flat)}d", *flat), 0)
        output_offset = 8 * len(flat)
        function(store, 0, len(rows), output_offset)
        raw = memory.read(store, output_offset, output_offset + 8 * outputs * len(rows))
        values = struct.unpack(f"<{outputs * len(rows)}d", bytes(raw))
        return [list(values[index : index + outputs]) for index in range(0, len(values), outputs)]

    def test_a_built_module_matches_a_hand_written_module(self):
        from workbench.wasm import add, build_wasm, const, feature, mul, var

        built = build_wasm(2, [var("out"), add(feature(1), var("out"))], lets=[("out", add(mul(feature(0), const(2.5)), const(1.0)))])
        import wasmtime

        example = wasmtime.wat2wasm(
            """
(module
  (memory (export "memory") 1)
  (func (export "predict") (param $x i32) (param $n i32) (param $y i32)
    (local $i i32)
    (local $out f64)
    (block $done
      (loop $next
        (br_if $done (i32.ge_u (local.get $i) (local.get $n)))
        (local.set $out
          (f64.add
            (f64.mul (f64.load (i32.add (local.get $x) (i32.shl (local.get $i) (i32.const 4)))) (f64.const 2.5))
            (f64.const 1.0)))
        (f64.store (i32.add (local.get $y) (i32.shl (local.get $i) (i32.const 4))) (local.get $out))
        (f64.store
          (i32.add (i32.add (local.get $y) (i32.shl (local.get $i) (i32.const 4))) (i32.const 8))
          (f64.add (f64.load (i32.add (i32.add (local.get $x) (i32.shl (local.get $i) (i32.const 4))) (i32.const 8))) (local.get $out)))
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $next)))))
"""
        )
        rows = [[1.0, 0.0], [2.0, 3.5], [3.0, 8.5], [-4.25, 100.0]]
        self.assertEqual(self.run_module(example, rows, 2), self.run_module(built, rows, 2))

    def test_a_select_chooses_by_comparison(self):
        from workbench.wasm import build_wasm, const, feature, lt, select

        built = build_wasm(1, [select(lt(feature(0), const(20.0)), const(1.0), const(2.0))])
        self.assertEqual([[1.0], [2.0], [2.0]], self.run_module(built, [[19.5], [20.0], [30.0]], 1))

    def test_a_maths_function_is_imported_and_runs_through_the_python_hosts(self):
        import math

        from asystem.model import build_signature, signature_input, signature_output
        from asystem.replay import model_predict
        from workbench.wasm import add, atan, build_wasm, const, exp, feature, log, mul, tanh

        built = build_wasm(1, [add(mul(atan(feature(0)), const(2.0)), const(1.0)), exp(feature(0)), log(feature(0)), tanh(feature(0))])
        path = join(tempfile.mkdtemp(), "model.wasm")
        with open(path, "wb") as model_file:
            model_file.write(built)
        signature = build_signature(
            "demo_calc",
            [signature_input("demo_in_seconds", "seconds", "Input.")],
            [signature_output(name, "seconds", "Output.", datatype="FP64") for name in ("demo_a_seconds", "demo_b_seconds", "demo_c_seconds", "demo_d_seconds")],
        )
        predict = model_predict(path, "wasm", signature)
        for value in (0.0, 0.5, 3.25, -2.0):
            answer = predict({"demo_in_seconds": [value]})
            self.assertEqual(math.atan(value) * 2.0 + 1.0, answer["demo_a_seconds"][0])
            self.assertEqual(math.exp(value), answer["demo_b_seconds"][0])
            self.assertEqual(math.tanh(value), answer["demo_d_seconds"][0])
        self.assertEqual(float("-inf"), predict({"demo_in_seconds": [0.0]})["demo_c_seconds"][0])
        self.assertTrue(math.isnan(predict({"demo_in_seconds": [-1.0]})["demo_c_seconds"][0]))
        self.assertEqual(float("inf"), predict({"demo_in_seconds": [1000.0]})["demo_b_seconds"][0])

    def predictor(self, built, names):
        from asystem.model import build_signature, signature_input, signature_output
        from asystem.replay import model_predict

        path = join(tempfile.mkdtemp(), "model.wasm")
        with open(path, "wb") as model_file:
            model_file.write(built)
        signature = build_signature("demo_calc", [signature_input("demo_in_seconds", "seconds", "Input.")], [signature_output(name, "seconds", "Output.", datatype="FP64") for name in names])
        return model_predict(path, "wasm", signature)

    def test_a_traced_function_gives_the_same_answers_as_a_plain_call_and_as_the_module(self):
        import math

        import numpy

        from workbench.wasm import atan, build_wasm, clip, floor, select, trace

        def capacity(voltage, scale, width, centre, offset):
            raw = scale * atan(width * (voltage - centre)) + offset
            return select(voltage < 3.0, 0.0, select(voltage > 3.9, 100.0, floor(clip(raw, 0.0, 100.0) / 5.0) * 5.0))

        outputs = trace(lambda voltage: capacity(voltage, 40.5, 9.5, 3.76, 56.7), 1)
        predict = self.predictor(build_wasm(1, outputs), ["demo_out_seconds"])
        for value in (*numpy.linspace(2.5, 4.2, 60).tolist(), 3.0, 3.9, float("inf"), float("-inf")):
            expected = capacity(value, 40.5, 9.5, 3.76, 56.7)
            self.assertEqual(expected, predict({"demo_in_seconds": [value]})["demo_out_seconds"][0], value)
        self.assertTrue(math.isnan(predict({"demo_in_seconds": [float("nan")]})["demo_out_seconds"][0]))
        self.assertEqual([capacity(value, 40.5, 9.5, 3.76, 56.7) for value in (2.0, 3.5, 4.0)], numpy.asarray(capacity(numpy.array([2.0, 3.5, 4.0]), 40.5, 9.5, 3.76, 56.7)).tolist())

    def test_operators_build_the_same_tree_as_the_helpers(self):
        from workbench.wasm import absolute, add, build_wasm, const, div, mul, neg, power, sub, trace

        by_operators = trace(lambda x: [2.0 * x + 1.0 - x / 4.0, -x, x**3, 2.0**x, abs(x) + (1.0 - x)], 1)
        by_helpers = trace(lambda x: [sub(add(mul(const(2.0), x), const(1.0)), div(x, const(4.0))), neg(x), mul(mul(x, x), x), power(const(2.0), x), add(absolute(x), sub(const(1.0), x))], 1)
        self.assertEqual([entry.node for entry in by_helpers], [entry.node for entry in by_operators])
        names = ["a_seconds", "b_seconds", "c_seconds", "d_seconds", "e_seconds"]
        answer = self.predictor(build_wasm(1, by_operators), names)({"demo_in_seconds": [3.0]})
        self.assertEqual([6.0 + 1.0 - 0.75, -3.0, 27.0, 8.0, 3.0 + -2.0], [answer[name][0] for name in names])

    def test_a_traced_function_may_return_several_outputs_and_take_several_features(self):
        from workbench.wasm import build_wasm, trace

        def accumulate(x, total):
            out = 2.5 * x + 1.0
            return out, total + out

        outputs = trace(accumulate, 2)
        self.assertEqual(2, len(outputs))
        answer = self.run_module(build_wasm(2, outputs), [[2.0, 10.0], [0.0, 0.0]], 2)
        self.assertEqual([[6.0, 16.0], [1.0, 1.0]], answer)

    def test_an_expression_refuses_python_control_flow_and_numpy_functions(self):
        from typing import Any

        import numpy

        from workbench.wasm import feature

        x: Any = feature(0)
        with self.assertRaises(TypeError):
            bool(x < 1.0)
        with self.assertRaises(TypeError):
            numpy.arctan(x)
        with self.assertRaises(TypeError):
            self.assertIsNone(x + "1")

    def test_every_maths_function_agrees_with_numpy_at_the_edges_of_its_domain(self):
        import math

        from asystem.model import WASM_MATH_FUNCTIONS
        from workbench import wasm

        edges = [0.0, -0.0, 0.5, -0.5, 1.0, -1.0, 2.0, -3.0, 710.0, -710.0, 1000.0, -1000.0, float("inf"), float("-inf"), float("nan")]
        rights = [-1.0, -2.0, 0.5, 2.0, 3.0, 1e300]
        for name, arity in WASM_MATH_FUNCTIONS.items():
            function = getattr(wasm, "power" if name == "pow" else name)
            for right in rights if arity == 2 else [None]:
                arguments = [wasm.feature(0), wasm.const(right)] if arity == 2 else [wasm.feature(0)]
                predict = self.predictor(wasm.build_wasm(1, [function(*arguments)]), ["demo_out_seconds"])
                for value in edges:
                    if name == "pow" and (value == float("-inf") or str(value) == "-0.0"):
                        continue
                    expected = function(value, right) if arity == 2 else function(value)
                    got = predict({"demo_in_seconds": [value]})["demo_out_seconds"][0]
                    label = f"{name} [{value}] [{right}] expected [{expected}] got [{got}]"
                    if math.isnan(expected):
                        self.assertTrue(math.isnan(got), label)
                    else:
                        self.assertTrue(got == expected or math.isclose(got, expected, rel_tol=1e-12, abs_tol=1e-300), label)
                        if expected == 0.0:
                            self.assertEqual(math.copysign(1.0, expected), math.copysign(1.0, got), label)

    def test_a_bad_expression_is_refused(self):
        from workbench.wasm import build_wasm

        with self.assertRaises(ValueError):
            build_wasm(1, [("x", 1)])
        with self.assertRaises(ValueError):
            build_wasm(1, [("var", "missing")])
        with self.assertRaises(ValueError):
            build_wasm(1, [("const", float("nan"))])
        with self.assertRaises(ValueError):
            build_wasm(1, [("cbrt", ("x", 0))])
        with self.assertRaises(ValueError):
            build_wasm(1, [("pow", ("x", 0))])


class ScratchProjectDirTest(unittest.TestCase):
    def test_a_run_without_an_output_directory_gets_a_temporary_project(self):
        from workbench.project import scratch_project_dir

        with mock.patch.dict(os.environ, {"MODEL_OUTPUT_DIR": ""}):
            self.assertTrue(scratch_project_dir("demo/calc/run").endswith("/project"))

    def test_a_run_with_an_output_directory_gets_a_fresh_project_under_it(self):
        from workbench.project import scratch_project_dir

        output_dir = tempfile.mkdtemp()
        stale = join(output_dir, "project", "demo/calc/run")
        os.makedirs(stale)
        open(join(stale, "old.json"), "w").close()
        self.assertEqual(stale, scratch_project_dir("demo/calc/run", output_dir))
        self.assertFalse(os.path.exists(stale))


class EnsureDataTest(unittest.TestCase):
    def test_a_dataset_is_built_once_and_then_read(self):
        from workbench.data import ensure_data

        notebook_dir = tempfile.mkdtemp()
        builds = []

        def build():
            builds.append(1)
            return {"x": [1.0, 2.0]}

        first, path = ensure_data("demo/calc/run", "training", "demo_training", build, "2026-11-03_10-00-00", notebook_dir)
        second, _ = ensure_data("demo/calc/run", "training", "demo_training", build, "2026-11-03_10-00-00", notebook_dir)
        self.assertEqual(1, len(builds))
        self.assertEqual(first.to_dicts(), second.to_dicts())
        self.assertTrue(os.path.isfile(path))

    def test_an_absent_dataset_without_a_builder_is_an_error(self):
        from workbench.data import ensure_data

        with self.assertRaises(FileNotFoundError):
            ensure_data("demo/calc/run", "backtest", "demo_backtest", None, "2026-11-03_10-00-00", tempfile.mkdtemp())


class ReplayRunnerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import subprocess

        env_fab = join(DIR_ROOT, "../../../.env_fab")
        script = (
            f". {env_fab} && export CARGO_HOME=$HOME/.rust/versions/asystem RUSTUP_HOME=$HOME/.rust/versions/asystem PATH=$HOME/.rust/versions/asystem/bin:$PATH "
            f"CARGO_TARGET_DIR={DIR_ROOT}/target/rust && (cd {DIR_ROOT}/src/main/rust/consumer && cargo build --quiet) && "
            f'(cd {DIR_ROOT}/src/main/go/consumer && "$GOROOT/bin/go" build -o {DIR_ROOT}/target/go/consumer .)'
        )
        build = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=900, check=False)
        cls.native = {"rust": join(DIR_ROOT, "target/rust/debug/consumer"), "go": join(DIR_ROOT, "target/go/consumer")}
        cls.runners = {**{host: [path] for host, path in cls.native.items()}, "python": [sys.executable, "-m", "consumer.main"]}
        if build.returncode != 0 or not all(os.path.isfile(path) for path in cls.native.values()):
            raise unittest.SkipTest(f"the Rust and Go consumers could not be built [{build.stderr.strip()[-200:]}]")

    def project(self, flavour, model_bytes=None, samples=None, tolerance=None):
        import wasmtime

        from asystem.model import build_signature, evaluate_acceptance, package_project, signature_input, signature_output

        work_dir = tempfile.mkdtemp()
        model_path = None
        constants = None
        if flavour == "wasm":
            model_path = join(work_dir, "model.wasm")
            wat = '(module (memory (export "memory") 1) (func (export "predict") (param i32 i32 i32) (f64.store (local.get 2) (f64.mul (f64.load (local.get 0)) (f64.const 2)))))'
            with open(model_path, "wb") as model_file:
                model_file.write(model_bytes if model_bytes is not None else wasmtime.wat2wasm(wat))
        elif flavour == "pyfunc":
            model_path = join(work_dir, "model.py")
            with open(model_path, "w") as model_file:
                model_file.write(
                    "import pandas as pd\nfrom mlflow.models import set_model\nfrom mlflow.pyfunc import PythonModel\n\n"
                    'class Double(PythonModel):\n    def predict(self, context, model_input: pd.DataFrame, params=None):\n        return pd.DataFrame({"demo_out": [x * 2.0 for x in model_input["demo_in"]]})\n\n\nset_model(Double())\n'
                )
        else:
            constants = {"demo_out": 4.0}
        signature = build_signature("demo_replay_double", [signature_input("demo_in", "none", "A number.")], [signature_output("demo_out", "none", "Twice the number.", datatype="FP64")])
        dataset = join(work_dir, "2026-11-03_10-00-00", "demo_replay_backtest_2026-11-01_2026-11-02.csv")
        os.makedirs(dirname(dataset))
        with open(dataset, "w") as dataset_file:
            dataset_file.write("a,b\n1,2\n")
        evaluation = None
        if flavour != "static":
            evaluation = evaluate_acceptance(lambda: [{"split": "backtest", "output": "demo_out", "name": "rmse", "value": 0.0, "limit": 1, "direction": "max"}], {"backtest": [dataset]})
        first = 4.0 if constants else 3.0
        samples = samples or [{"demo_in": 1.5, "demo_out": first}, {"demo_in": 2.0, "demo_out": 4.0}, {"demo_in": None, "expect": "error"}]
        project_dir = join(work_dir, "project")
        package_project(
            project_dir,
            "demo_replay_double",
            flavour,
            signature,
            samples,
            {"source": "manual", "inputs": [], "implementation": "demo built by hand"},
            constants=constants,
            model_path=model_path,
            evaluation=evaluation,
            tolerance=tolerance,
        )
        return project_dir

    def run_runner(self, host, project_dir):
        import subprocess

        return subprocess.run([*self.runners[host], project_dir], capture_output=True, text=True, timeout=120, check=False, cwd=join(DIR_ROOT, "src/main/python"))

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
        for flavour in ("static", "wasm"):
            project_dir = self.project(flavour)
            for host in self.runners:
                completed = self.run_runner(host, project_dir)
                self.assertEqual(0, completed.returncode, f"{host} {flavour} {completed.stderr}")

    def test_each_runner_skips_a_flavour_it_does_not_support(self):
        project_dir = self.project("pyfunc")
        for host in self.native:
            self.assertEqual(1, self.run_runner(host, project_dir).returncode, host)

    def test_each_runner_provides_the_maths_functions_within_a_stated_tolerance(self):
        import math

        from workbench.wasm import atan, build_wasm, feature

        samples = [{"demo_in": 1.5, "demo_out": math.atan(1.5)}, {"demo_in": 2.0, "demo_out": math.atan(2.0)}, {"demo_in": None, "expect": "error"}]
        project_dir = self.project("wasm", model_bytes=build_wasm(1, [atan(feature(0))]), samples=samples, tolerance={"demo_out": {"absolute": 1e-12}})
        for host in self.runners:
            completed = self.run_runner(host, project_dir)
            self.assertEqual(0, completed.returncode, f"{host} {completed.stderr}")

    def test_each_runner_provides_every_maths_function_within_a_stated_tolerance(self):
        from asystem.model import WASM_MATH_FUNCTIONS
        from workbench import wasm

        for name, arity in WASM_MATH_FUNCTIONS.items():
            function = getattr(wasm, "power" if name == "pow" else name)
            tree = function(wasm.feature(0), wasm.const(1.5)) if arity == 2 else function(wasm.feature(0))
            samples = [{"demo_in": value, "demo_out": function(value, 1.5) if arity == 2 else function(value)} for value in (0.25, 0.5, 0.9)]
            project_dir = self.project("wasm", model_bytes=wasm.build_wasm(1, [tree]), samples=[*samples, {"demo_in": None, "expect": "error"}], tolerance={"demo_out": {"absolute": 1e-12}})
            for host in self.runners:
                completed = self.run_runner(host, project_dir)
                self.assertEqual(0, completed.returncode, f"{name} {host} {completed.stdout} {completed.stderr}")

    def test_each_runner_rejects_a_response_that_differs_from_the_golden(self):
        for flavour in ("static", "wasm"):
            project_dir = self.project(flavour)
            self.retouch(project_dir, lambda golden: golden["sequences"][0]["steps"][0]["response"]["outputs"][0]["data"].__setitem__(0, 99.0))
            for host in self.runners:
                completed = self.run_runner(host, project_dir)
                self.assertEqual(1, completed.returncode, f"{host} {flavour}")
                self.assertIn("RP003", completed.stderr)

    def test_each_runner_applies_a_stated_tolerance(self):
        def tolerate(shift):
            def change(golden):
                golden["tolerance"] = {"demo_out": {"absolute": 1e-3}}
                golden["sequences"][0]["steps"][1]["response"]["outputs"][0]["data"][0] += shift

            return change

        for flavour in ("static", "wasm"):
            near, far = self.project(flavour), self.project(flavour)
            self.retouch(near, tolerate(1e-6))
            self.retouch(far, tolerate(0.5))
            for host in self.runners:
                self.assertEqual(0, self.run_runner(host, near).returncode, f"{host} {flavour}")
                self.assertEqual(1, self.run_runner(host, far).returncode, f"{host} {flavour}")

    def test_each_runner_rejects_a_file_that_differs_from_its_manifest_hash(self):
        project_dir = self.project("wasm")
        with open(join(project_dir, "golden.json"), "a") as golden_file:
            golden_file.write(" ")
        for host in self.runners:
            completed = self.run_runner(host, project_dir)
            self.assertEqual(1, completed.returncode, host)
            self.assertIn("PJ003", completed.stderr)


class ConsumerSourceTest(unittest.TestCase):
    def test_the_python_consumer_loads_projects_with_the_same_source_as_mlserver(self):
        for name in ("run_static", "run_wasm", "run_onnx", "run_pyfunc"):
            with open(join(DIR_ROOT, f"src/main/python/consumer/{name}.py"), "rb") as consumer_file, open(join(DIR_ROOT, f"../../may/mlserver/src/main/python/serving/{name}.py"), "rb") as served_file:
                self.assertEqual(served_file.read(), consumer_file.read(), name)

    def test_every_host_provides_exactly_the_maths_functions_of_the_spec(self):
        import re

        from asystem.model import WASM_MATH_FUNCTIONS

        def read(path):
            with open(join(DIR_ROOT, path)) as source_file:
                return source_file.read()

        go = {name: 2 if name in ("atan2", "pow") else 1 for name in re.findall(r'"(\w+)": math\.', read("src/main/go/consumer/run_webassembly.go"))}
        rust_source = read("src/main/rust/consumer/src/run_wasm.rs")
        rust = {
            name: arity
            for arity, kind in ((1, "unary"), (2, "binary"))
            for name in re.findall(r'\("(\w+)", f64::\w+\)', rust_source.split(f"let {kind}:")[1].split("];")[0] if kind == "unary" else rust_source.split(f"let {kind}:")[1].split(";\n")[0])
        }
        python = dict(re.findall(r'"(\w+)": (\d)', read("src/main/python/consumer/run_wasm.py").split("arities = ")[1].split("}")[0]))
        python = {name: int(arity) for name, arity in python.items()}
        for host, found in (("go", go), ("rust", rust), ("python", python)):
            self.assertTrue(found, host)
            self.assertEqual(sorted(WASM_MATH_FUNCTIONS), sorted(found), host)
        self.assertEqual(WASM_MATH_FUNCTIONS, python)
        self.assertEqual({name for name, arity in WASM_MATH_FUNCTIONS.items() if arity == 2}, {name for name, arity in rust.items() if arity == 2})

    def test_every_consumer_main_reports_the_same_stages_in_the_same_shape(self):
        import contextlib
        import io
        import re

        from consumer.main import main

        line = r"    (verify|load|replay)\s+ \.\.\. done \[[^\]]+\] \(\d+\.\d\ds\)"
        project = join(DIR_ROOT, "src/main/notebook/example/static/constant/project")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, main([project]))
        matches = [re.fullmatch(line, entry) for entry in output.getvalue().splitlines()]
        self.assertEqual(["verify", "load", "replay"], [match.group(1) for match in matches if match])
        self.assertEqual(3, len(matches))
        for path, forms in (
            ("src/main/go/consumer/main.go", ('report("verify"', 'report("load"', 'report("replay"', '"    %-12s ... done [%s] (%.2fs)\\n"')),
            ("src/main/rust/consumer/src/main.rs", ('report("verify"', 'report("load"', 'report("replay"', '"    {stage:<12} ... done [{detail}] ({:.2}s)"')),
        ):
            with open(join(DIR_ROOT, path)) as source_file:
                source = re.sub(r"\s+", "", source_file.read())
            for form in forms:
                self.assertIn(re.sub(r"\s+", "", form), source, path)


if __name__ == "__main__":
    sys.exit(run_pytest("datascience/unittest", ["-s", "-o", f"cache_dir={join(DIR_ROOT, 'target/.pytest_cache')}", __file__]))
