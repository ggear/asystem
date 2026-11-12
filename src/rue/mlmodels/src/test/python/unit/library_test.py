import contextlib
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from os.path import basename, dirname, join, realpath

ROOT = realpath(join(dirname(__file__), "../../../../../.."))
sys.path.insert(0, join(ROOT, "rue/mlmodels/src/main/python"))


class ModelProjectTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(contextlib.chdir(fresh_mlruns_dir()))
        from mlmodels._signature import build_signature, golden_document, golden_step, signature_input, signature_output

        self.project_dir = join(tempfile.mkdtemp(), "project")
        self.signature = build_signature(
            "demo_calc",
            [signature_input("demo_clock_seconds", "seconds", "Time of the call."), signature_input("demo_state_in", "state", "Carried state.", required=False, shape=[-1])],
            [signature_output("demo_limit_seconds", "seconds", "A limit."), signature_output("demo_state_out", "state", "Next state.", required=False, shape=[-1])],
            state=[{"name": "last_seconds", "unit": "seconds", "description": "The previous call."}],
        )
        steps = [
            golden_step(self.signature, "s-0", {"demo_clock_seconds": 10.0}, {"demo_limit_seconds": 5}),
            golden_step(self.signature, "s-1", {"demo_clock_seconds": 11.0, "demo_state_in": [10.0]}, {"demo_limit_seconds": 5}),
            golden_step(self.signature, "s-2", {"demo_state_in": [10.0]}, error="signature"),
        ]
        self.golden = golden_document([("calls", steps)])

    def write(self, **overrides):
        from mlmodels._project import write_project

        arguments = {
            "project_dir": self.project_dir,
            "name": "demo_calc",
            "flavour": "static",
            "signature": self.signature,
            "golden": self.golden,
            "provenance": {"source": "manual", "inputs": []},
            "constants": {"demo_limit_seconds": 5},
        }
        return write_project(**{**arguments, **overrides})

    def rules(self, **overrides):
        from mlmodels._lint_project import lint_project

        with contextlib.suppress(ValueError):
            self.write(**overrides)
        return sorted({rule for rule, _ in lint_project(self.project_dir)})

    def test_valid_project_has_no_findings(self):
        self.assertEqual("static", self.write()["flavour"])
        self.assertEqual([], self.rules())

    def test_tampered_file_is_found(self):
        self.write()
        with open(join(self.project_dir, "golden.json"), "a") as golden:
            golden.write(" ")
        from mlmodels._lint_project import lint_project

        self.assertEqual(["PJ003"], sorted({rule for rule, _ in lint_project(self.project_dir)}))

    def test_unknown_flavour_and_source_are_found(self):
        self.assertEqual(["PJ002"], self.rules(flavour="guess", provenance={"source": "guess", "inputs": []}))

    def test_provenance_inputs_must_be_a_list(self):
        self.assertEqual(["PJ002"], self.rules(provenance={"source": "manual"}))

    def test_model_flavour_needs_its_file(self):
        self.assertEqual(["PJ003"], self.rules(flavour="wasm", evaluation=self.evaluation(), provenance={"source": "manual", "inputs": [], "implementation": "demo model.py requires pandas"}))

    def test_model_file_is_copied_into_the_project_and_hashed(self):
        model_path = self.model_file()
        manifest = self.write(
            flavour="pyfunc",
            model_path=model_path,
            constants=None,
            evaluation=self.evaluation(),
            provenance={"source": "manual", "inputs": [], "implementation": "demo model.py requires pandas"},
        )
        self.assertEqual(("model.py", True), (manifest["model"], "model.py" in manifest["files"]))
        self.assertTrue(os.path.isfile(join(self.project_dir, "model.py")))

    def test_implementation_must_say_something(self):
        for implementation in ("demo", "TBD", "to be determined", "", None):
            self.assertEqual(["PJ002", "PJ003"], self.rules(flavour="wasm", evaluation=self.evaluation(), provenance={"source": "manual", "inputs": [], "implementation": implementation}))

    def test_a_wasm_module_may_import_only_the_maths_functions(self):
        import wasmtime

        from mlmodels._lint_project import lint_project

        def rules(wat):
            project_dir = build_project("wasm")
            with open(join(project_dir, "model.wasm"), "wb") as model_file:
                model_file.write(wasmtime.wat2wasm(wat))
            return {rule for rule, _ in lint_project(project_dir)}

        body = '(memory (export "memory") 1) (func (export "predict") (param i32 i32 i32))'
        self.assertNotIn("PJ016", rules(f'(module (import "asystem_math" "atan" (func (param f64) (result f64))) {body})'))
        self.assertIn("PJ016", rules(f'(module (import "env" "atan" (func (param f64) (result f64))) {body})'))
        self.assertIn("PJ016", rules(f'(module (import "asystem_math" "pow" (func (param f64) (result f64))) {body})'))
        self.assertIn("PJ016", rules(f'(module (import "asystem_math" "atan" (func (param f64 f64) (result f64))) {body})'))

    def test_a_pyfunc_declares_the_packages_its_model_imports_beyond_the_base(self):
        def rules(source, python_deps):
            model_path = join(tempfile.mkdtemp(), "model.py")
            with open(model_path, "w") as model_file:
                model_file.write(source)
            return self.rules(flavour="pyfunc", model_path=model_path, python_deps=python_deps)

        body = "import json\nimport pandas\nfrom mlflow.models import set_model\n"
        self.assertNotIn("PJ017", rules(body, []))
        self.assertNotIn("PJ017", rules(body + "import polars as pl\n", ["polars"]))
        self.assertNotIn("PJ017", rules(body + "from sklearn.linear_model import Ridge\n", ["Scikit-Learn"]))
        self.assertIn("PJ017", rules(body + "import polars as pl\n", []))
        self.assertIn("PJ017", rules(body, ["polars"]))
        self.assertIn("PJ017", rules(body, ["pandas"]))

    def test_a_wasm_runtime_must_equal_the_module_imports(self):
        import wasmtime

        from mlmodels._lint_project import lint_project

        project_dir = build_project("wasm")
        with open(join(project_dir, "model.wasm"), "wb") as model_file:
            model_file.write(wasmtime.wat2wasm('(module (import "asystem_math" "tanh" (func (param f64) (result f64))) (memory (export "memory") 1) (func (export "predict") (param i32 i32 i32)))'))
        with open(join(project_dir, "project.json")) as manifest_file:
            manifest = json.load(manifest_file)
        self.assertEqual({"wasm": []}, manifest["runtime"])
        self.assertIn("PJ017", {rule for rule, _ in lint_project(project_dir)})
        for runtime, expected in (({"wasm": ["tanh"]}, False), ({"wasm": ["sin"]}, True), ({"wasm": ["tanh"], "python": []}, True), ({}, True)):
            with open(join(project_dir, "project.json"), "w") as manifest_file:
                json.dump({**manifest, "runtime": runtime}, manifest_file)
            self.assertEqual(expected, "PJ017" in {rule for rule, _ in lint_project(project_dir)})

    def test_a_flavour_with_no_runtime_takes_no_python_dependencies(self):
        with self.assertRaises(ValueError):
            self.write(python_deps=["polars"])
        self.write()
        with open(join(self.project_dir, "project.json")) as manifest_file:
            manifest = json.load(manifest_file)
        with open(join(self.project_dir, "project.json"), "w") as manifest_file:
            json.dump({**manifest, "runtime": {"python": []}}, manifest_file)
        from mlmodels._lint_project import lint_project

        self.assertEqual(["PJ017"], sorted({rule for rule, _ in lint_project(self.project_dir)}))

    def test_pyfunc_project_is_registered_as_a_pyfunc_model(self):
        from mlmodels._registry import register_project, registry_pull
        from mlmodels._signature import build_signature, golden_document, golden_step, signature_input, signature_output

        signature = build_signature(
            "demo_calc",
            [signature_input("demo_in_seconds", "seconds", "Input."), signature_input("demo_extra_seconds", "seconds", "Optional input.", required=False)],
            [signature_output("demo_out_seconds", "seconds", "Output.")],
        )
        golden = golden_document([("calls", [golden_step(signature, "s-0", {"demo_in_seconds": 1.0}, {"demo_out_seconds": 2.0}), golden_step(signature, "s-1", {}, error="signature")])])
        model_path = join(tempfile.mkdtemp(), "model.py")
        with open(model_path, "w") as model_file:
            model_file.write(
                "import pandas as pd\nfrom mlflow.models import set_model\nfrom mlflow.pyfunc import PythonModel\n\n\n"
                "class Demo(PythonModel):\n    def predict(self, context, model_input: pd.DataFrame, params=None):\n"
                '        return pd.DataFrame({"demo_out_seconds": model_input["demo_in_seconds"] * 2})\n\n\nset_model(Demo())\n'
            )
        self.write(
            flavour="pyfunc",
            model_path=model_path,
            signature=signature,
            golden=golden,
            constants=None,
            evaluation=self.evaluation(output="demo_out_seconds"),
            provenance={"source": "manual", "inputs": [], "implementation": "demo model.py requires pandas"},
        )
        root_dir = tempfile.mkdtemp()
        uri = f"sqlite:///{join(root_dir, 'mlflow.db')}"
        import mlflow.pyfunc

        version = register_project(self.project_dir, "demo_calc", uri, snapshot_version="10.200.1951-SNAPSHOT")
        mlflow.set_tracking_uri(uri)
        client = mlflow.MlflowClient()
        registered = client.get_model_version("demo_calc", str(version))
        self.assertEqual("10.200.1951-SNAPSHOT", registered.tags["snapshot_version"])
        assert registered.run_id is not None
        self.assertEqual("mlmodels", client.get_run(registered.run_id).data.tags["mlflow.source.name"])
        register_project(self.project_dir, "demo_calc", uri, snapshot_version="10.200.1952-SNAPSHOT")
        self.assertEqual("10.200.1951-SNAPSHOT", client.get_model_version("demo_calc", str(version)).tags["snapshot_version"])
        loaded = mlflow.pyfunc.load_model("models:/demo_calc@preview")
        self.assertEqual([2.0], list(loaded.predict({"demo_in_seconds": [1.0]})["demo_out_seconds"]))
        input_schema = loaded.metadata.get_input_schema()
        assert input_schema is not None
        columns = {column.name: column.required for column in input_schema.inputs}
        self.assertEqual({"demo_in_seconds": True, "demo_extra_seconds": False}, columns)
        pulled = registry_pull("demo_calc", "preview", join(root_dir, "pulled"), uri)
        assert pulled is not None
        self.assertEqual("pyfunc", pulled["flavour"])
        self.assertEqual("1", str(version))

    def test_pyfunc_registration_refuses_a_state_vector_signature(self):
        from mlmodels._registry import register_project

        model_path = self.model_file()
        self.write(
            flavour="pyfunc",
            model_path=model_path,
            constants=None,
            evaluation=self.evaluation(),
            provenance={"source": "manual", "inputs": [], "implementation": "demo model.py requires pandas"},
        )
        with self.assertRaises(ValueError):
            register_project(self.project_dir, "demo_calc", f"sqlite:///{join(tempfile.mkdtemp(), 'mlflow.db')}")

    def model_file(self, flavour="pyfunc"):
        path = join(tempfile.mkdtemp(), {"wasm": "model.wasm", "onnx": "model.onnx"}.get(flavour, "model.py"))
        if flavour == "wasm":
            with open(path, "wb") as model_file:
                model_file.write(b"\0asm\x01\x00\x00\x00")
        elif flavour == "onnx":
            import onnx
            from onnx import TensorProto, helper

            node = helper.make_node("Identity", ["x"], ["y"])
            graph = helper.make_graph([node], "demo", [helper.make_tensor_value_info("x", TensorProto.DOUBLE, [1])], [helper.make_tensor_value_info("y", TensorProto.DOUBLE, [1])])
            onnx.save(helper.make_model(graph), path)
        else:
            with open(path, "w") as model_file:
                model_file.write("VALUE = 1\n")
        return path

    def evaluation(self, passing=True, output="demo_limit_seconds", checks=None):
        from mlmodels._project import evaluation_build

        dataset_dir = join(tempfile.mkdtemp(), "2026-11-03_10-00-00")
        os.makedirs(dataset_dir)
        dataset = join(dataset_dir, "demo_calc_limit_2026-11-01_2026-11-02.csv")
        with open(dataset, "w") as dataset_file:
            dataset_file.write("a,b\n1,2\n")
        value = 0.5 if passing else 9.0
        return evaluation_build(lambda: checks or [{"split": "backtest", "output": output, "name": "rmse", "value": value, "limit": 1.0, "direction": "max"}], {"backtest": [dataset]})

    def test_folds_in_an_evaluation_are_well_formed_and_their_metrics_gated_by_mean_and_worst(self):
        folds = [{"fold": index, "scheme": "forward", "gap": 1, "training": 10, "validation": 5, "rmse": 0.5 + index} for index in range(3)]
        checks = [{"split": "backtest", "output": "demo_limit_seconds", "name": name, "value": 0.5, "limit": 1.0, "direction": "max"} for name in ("rmse", "rmse_mean", "rmse_worst")]
        evaluation = self.evaluation(checks=checks)
        self.assertNotIn("AC004", self.rules(evaluation={**evaluation, "folds": folds}))
        self.assertIn("AC004", self.rules(evaluation={**evaluation, "folds": [{**folds[0], "fold": 1}, *folds[1:]]}))
        self.assertIn("AC004", self.rules(evaluation={**evaluation, "folds": [{**folds[0], "scheme": "shuffled"}, *folds[1:]]}))
        self.assertIn("AC004", self.rules(evaluation={**evaluation, "folds": [{**folds[0], "gap": -1}, *folds[1:]]}))
        self.assertIn("AC004", self.rules(evaluation={**evaluation, "folds": [{**folds[0], "mae": 1.0}, *folds[1:]]}))
        ungated = self.evaluation(checks=[checks[0], checks[1]])
        self.assertIn("AC004", self.rules(evaluation={**ungated, "folds": folds}))
        self.assertIn("AC004", self.rules(evaluation={**evaluation, "folds": []}))

    def test_an_evaluation_says_whether_it_is_independent_and_a_validation_gate_needs_no_backtest(self):
        import json as _json

        from mlmodels._project import evaluation_build

        dataset = join(tempfile.mkdtemp(), "1", "demo_calc_limit.csv")
        os.makedirs(os.path.dirname(dataset))
        with open(dataset, "w") as dataset_file:
            dataset_file.write("a,b\n1,2\n")

        def build(split, gate, datasets):
            return evaluation_build(lambda: [{"split": split, "output": "demo_limit_seconds", "name": "rmse", "value": 0.5, "limit": 1.0, "direction": "max", "gate": gate}], datasets)

        validation_only = build("validation", True, {"validation": [dataset]})
        self.assertIs(False, validation_only["independent"])
        self.assertNotIn("AC005", self.rules(evaluation=validation_only))
        both = build("backtest", True, {"validation": [dataset], "backtest": [dataset]})
        self.assertIs(True, both["independent"])
        self.assertNotIn("AC005", self.rules(evaluation=both))
        gated_validation = build("validation", True, {"validation": [dataset], "backtest": [dataset]})
        self.assertIn("AC005", self.rules(evaluation=gated_validation))
        self.assertNotIn("AC005", self.rules(evaluation=build("validation", False, {"validation": [dataset], "backtest": [dataset]})))
        self.assertIn("AC005", self.rules(evaluation={**validation_only, "independent": True}))
        self.assertIn("AC005", self.rules(evaluation=_json.loads(_json.dumps({k: v for k, v in both.items() if k != "independent"}))))

    def test_measure_matches_the_definitions(self):
        from mlmodels.workflow.evaluate import evaluate_metrics

        measures = evaluate_metrics([1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 6.0])
        self.assertAlmostEqual(1.0, measures["rmse"])
        self.assertAlmostEqual(0.5, measures["mae"])
        self.assertAlmostEqual(2.0, measures["max_abs_error"])
        self.assertAlmostEqual(0.5, measures["bias"])
        self.assertAlmostEqual(1.0 - 4.0 / 5.0, measures["r2"])
        self.assertAlmostEqual(8.0 / 70.0**0.5, measures["pearson_r"])
        constant = evaluate_metrics([2.0, 2.0], [2.0, 3.0])
        self.assertIsNone(constant["r2"])
        self.assertIsNone(constant["pearson_r"])
        with self.assertRaises(ValueError):
            evaluate_metrics([1.0], [1.0, 2.0])

    def test_outcome_and_budget_follow_the_value_limit_and_direction(self):
        evaluation = self.evaluation()
        self.assertEqual((True, 0.5, 0.5), (evaluation["passed"], evaluation["budget"], evaluation["checks"][0]["budget"]))
        self.assertEqual("2026-11-03_10-00-00/demo_calc_limit_2026-11-01_2026-11-02.csv", evaluation["datasets"]["backtest"][0]["path"])
        failing = self.evaluation(passing=False)
        self.assertEqual((False, 9.0), (failing["passed"], failing["budget"]))
        checks = [
            {"split": "backtest", "output": "demo_limit_seconds", "name": "recall", "value": 0.8, "limit": 0.5, "direction": "min"},
            {"split": "backtest", "output": "demo_limit_seconds", "name": "over", "value": -2.0, "limit": 0.0, "direction": "max"},
            {"split": "validation", "output": "demo_limit_seconds", "name": "mae", "value": 99.0, "limit": 1.0, "direction": "max", "gate": False},
        ]
        mixed = self.evaluation(checks=checks)
        self.assertEqual([True, True, False], [entry["passed"] for entry in mixed["checks"]])
        self.assertEqual([0.625, 0.0, 99.0], [entry["budget"] for entry in mixed["checks"]])
        self.assertEqual((True, 0.625), (mixed["passed"], mixed["budget"]))
        unmeasured = self.evaluation(checks=[{"split": "backtest", "output": "demo_limit_seconds", "name": "rmse", "value": None, "limit": 1.0, "direction": "max"}])
        self.assertEqual((False, None), (unmeasured["passed"], unmeasured["budget"]))

    def test_a_malformed_check_is_refused(self):
        base = {"split": "backtest", "output": "demo_limit_seconds", "name": "rmse", "value": 1.0, "limit": 1.0, "direction": "max"}
        for checks in ([], None, [{**base, "direction": "avg"}], [{**base, "limit": -1.0}], [{**base, "direction": "min", "limit": 0}], [{**base, "limit": "1"}]):
            with self.assertRaises(ValueError, msg=checks):
                self.evaluation(checks=checks) if checks else __import__("mlmodels._project", fromlist=["x"]).evaluation_build(lambda checks=checks: checks, {})

    def test_project_with_an_evaluation_has_no_findings(self):
        manifest = self.write(evaluation=self.evaluation())
        self.assertEqual(["evaluation.json", "golden.json", "signature.json"], sorted(manifest["files"]))
        self.assertEqual([], self.rules(evaluation=self.evaluation()))

    def test_a_model_project_without_an_evaluation_is_refused(self):
        self.assertEqual(["AC001"], self.rules(**{**self.fitted_overrides(), "evaluation": None}))

    def test_every_required_output_needs_a_gating_check(self):
        checks = [{"split": "backtest", "output": "demo_limit_seconds", "name": "rmse", "value": 0.5, "limit": 1.0, "direction": "max", "gate": False}]
        self.assertEqual(["AC001"], self.rules(evaluation=self.evaluation(checks=checks)))

    def test_checks_are_validated(self):
        base = {"split": "backtest", "output": "demo_limit_seconds", "name": "rmse", "value": 0.5, "limit": 1.0, "direction": "max"}
        for entry in ({**base, "split": "training"}, {**base, "name": "Bad-Name"}, {**base, "output": "demo_other_seconds"}):
            self.assertIn("AC002", self.rules(evaluation=self.evaluation(checks=[entry, {**base, "name": "mae"}])), entry)
        evaluation = self.evaluation()
        evaluation["checks"][0]["gate"] = "yes"
        self.assertIn("AC002", self.rules(evaluation=evaluation))
        evaluation = self.evaluation()
        evaluation["checks"][0]["value"] = "0.5"
        self.assertIn("AC002", self.rules(evaluation=evaluation))

    def test_a_tampered_evaluation_is_found(self):
        evaluation = self.evaluation(passing=False)
        evaluation["checks"][0]["passed"] = True
        self.assertIn("AC003", self.rules(evaluation=evaluation))
        evaluation = self.evaluation(passing=False)
        evaluation["passed"] = True
        self.assertIn("AC003", self.rules(evaluation=evaluation))
        evaluation = self.evaluation()
        evaluation["budget"] = 0.1
        self.assertIn("AC003", self.rules(evaluation=evaluation))
        evaluation = self.evaluation()
        del evaluation["datasets"]["backtest"]
        self.assertIn("AC003", self.rules(evaluation=evaluation))

    def test_registration_logs_metrics_datasets_and_the_verdict(self):
        import mlflow
        from mlmodels._registry import register_project

        self.write(evaluation=self.evaluation())
        uri = f"sqlite:///{join(tempfile.mkdtemp(), 'mlflow.db')}"
        register_project(self.project_dir, "demo_calc", uri)
        mlflow.set_tracking_uri(uri)
        run = mlflow.search_runs(experiment_names=["demo_calc"], output_format="list")[0]
        self.assertEqual(("passed", "0.5"), (run.data.tags["acceptance"], run.data.tags["acceptance_budget"]))
        self.assertEqual((1.0, 0.5, 0.5), (run.data.metrics["acceptance_passed"], run.data.metrics["acceptance_budget"], run.data.metrics["backtest/demo_limit_seconds/rmse"]))
        assert run.inputs is not None
        self.assertEqual("backtest", run.inputs.dataset_inputs[0].tags[0].value)

    def other_project(self, **overrides):
        other_dir = join(tempfile.mkdtemp(), "project")
        with contextlib.suppress(ValueError):
            self.write(project_dir=other_dir, **overrides)
        return other_dir

    def fitted_overrides(self, passing=True):
        model_path = self.model_file("wasm")
        return {
            "flavour": "wasm",
            "model_path": model_path,
            "constants": None,
            "evaluation": self.evaluation(passing=passing),
            "provenance": {"source": "manual", "inputs": [], "implementation": "demo module built by hand"},
        }

    def test_release_check_needs_a_passing_evaluation(self):
        from mlmodels._errors import GateError
        from mlmodels._project import check_acceptance
        from mlmodels._registry import check_release

        self.write()
        self.assertEqual([], check_release(self.project_dir))
        unevaluated = build_project("wasm")
        os.remove(join(unevaluated, "evaluation.json"))
        self.assertEqual(["PM004"], [rule for rule, _ in check_acceptance(unevaluated)])
        with self.assertRaises(GateError) as raised:
            self.write(**self.fitted_overrides(passing=False))
        self.assertEqual(("Evaluate", "acceptance"), (raised.exception.stage, raised.exception.gate))
        self.assertEqual(["PM004"], [rule for rule, _ in check_release(self.project_dir)])
        self.write(**self.fitted_overrides())
        self.assertEqual([], check_release(self.project_dir))

    def test_a_project_registers_again_after_its_experiment_and_model_were_deleted(self):
        import mlflow
        from mlmodels._registry import register_project

        self.write()
        uri = f"sqlite:///{join(tempfile.mkdtemp(), 'mlflow.db')}"
        register_project(self.project_dir, "demo_calc", uri)
        client = mlflow.MlflowClient()
        client.delete_registered_model("demo_calc")
        experiment = client.get_experiment_by_name("demo_calc")
        assert experiment is not None
        client.delete_experiment(experiment.experiment_id)
        version = register_project(self.project_dir, "demo_calc", uri)
        self.assertEqual("1", str(version))
        self.assertEqual("1", str(client.get_model_version_by_alias("demo_calc", "preview").version))

    def test_registering_an_unchanged_project_creates_nothing_new(self):
        import mlflow
        from mlmodels._registry import register_project

        self.write()
        uri = f"sqlite:///{join(tempfile.mkdtemp(), 'mlflow.db')}"
        first = register_project(self.project_dir, "demo_calc", uri)
        second = register_project(self.project_dir, "demo_calc", uri, aliases=("preview", "release"))
        self.assertEqual(first, second)
        mlflow.set_tracking_uri(uri)
        self.assertEqual(1, len(mlflow.search_runs(experiment_names=["demo_calc"])))
        self.assertEqual(second, mlflow.MlflowClient().get_model_version_by_alias("demo_calc", "release").version)
        self.write(provenance={"source": "manual", "inputs": [], "notes": "changed"})
        self.assertNotEqual(first, register_project(self.project_dir, "demo_calc", uri))

    def test_a_measured_check_needs_a_recorded_dataset(self):
        from mlmodels._project import evaluation_build

        measured = evaluation_build(lambda: [{"split": "backtest", "output": "demo_limit_seconds", "name": "rmse", "value": 0.1, "limit": 1.0, "direction": "max"}], {"backtest": []})
        self.assertIn("AC003", self.rules(evaluation=measured))
        unmeasured = evaluation_build(lambda: [{"split": "backtest", "output": "demo_limit_seconds", "name": "rmse", "value": None, "limit": 1.0, "direction": "max"}], {"backtest": []})
        self.assertNotIn("AC003", self.rules(evaluation=unmeasured))

    def test_static_flavour_refuses_a_model_file(self):
        with self.assertRaises(ValueError):
            self.write(model_path=join(self.project_dir, "signature.json"))

    def test_model_flavour_needs_its_implementation(self):
        self.assertEqual(["PJ002", "PJ003"], self.rules(flavour="wasm", evaluation=self.evaluation()))

    def test_name_must_match_signature_and_style(self):
        self.assertIn("PJ004", self.rules(name="Demo-Calc"))

    def test_output_must_end_with_the_unit_suffix(self):
        self.signature["outputs"][0]["name"] = "other_limit"
        self.assertIn("PJ007", self.rules(constants={"other_limit": 5}))

    def test_constant_outside_signature_is_found(self):
        self.assertIn("PJ008", self.rules(constants={"demo_limit_seconds": 5, "demo_misspelt_seconds": 1}))

    def test_static_must_cover_required_outputs(self):
        self.assertIn("PJ008", self.rules(constants={}))

    def test_golden_step_must_have_required_inputs(self):
        del self.golden["sequences"][0]["steps"][0]["request"]["inputs"][0]
        self.assertIn("PJ010", self.rules())

    def test_golden_needs_an_error_step_and_a_stateless_first_call(self):
        del self.golden["sequences"][0]["steps"][2]
        self.assertEqual(["PJ011"], self.rules())
        del self.golden["sequences"][0]["steps"][0]
        self.assertEqual(["PJ011"], self.rules())

    def test_static_responses_must_equal_the_constants(self):
        self.golden["sequences"][0]["steps"][0]["response"]["outputs"][0]["data"] = [6]
        self.assertEqual(["PJ012"], self.rules())

    def test_package_project_builds_golden_from_samples(self):
        from mlmodels._lint_project import lint_project
        from mlmodels._project import package_project

        rows = [
            {"demo_clock_seconds": 10.0, "expect": "ok"},
            {"demo_clock_seconds": 11.0, "demo_state_in": "10.0 11.0", "expect": "ok"},
            {"expect": "error"},
        ]
        manifest = package_project(self.project_dir, "demo_calc", "static", self.signature, rows, {"source": "manual", "inputs": []}, constants={"demo_limit_seconds": 5})
        self.assertEqual("static", manifest["flavour"])
        self.assertEqual([], lint_project(self.project_dir))

    def test_render_rust_names_every_tensor_with_optional_fields(self):
        from mlmodels._signature import render_rust

        rust = render_rust(self.signature)
        self.assertIn("pub demo_clock_seconds: f64,", rust)
        self.assertIn("pub demo_state_in: Option<Vec<f64>>,", rust)
        self.assertIn('pub const REQUIRED_OUTPUT_NAMES: &[&str] = &["demo_limit_seconds"];', rust)

    def test_render_go_and_python_name_every_tensor_with_optional_fields(self):
        from mlmodels._signature import render_go, render_python

        go = render_go(self.signature, "contract")
        self.assertIn("package contract", go)
        self.assertIn('DemoClockSeconds float64 `json:"demo_clock_seconds"`', go)
        self.assertIn('DemoStateIn []float64 `json:"demo_state_in,omitempty"`', go)
        self.assertIn('var RequiredOutputNames = []string{"demo_limit_seconds"}', go)
        python = render_python(self.signature)
        compile(python, "contract", "exec")
        self.assertIn("    demo_clock_seconds: float\n", python)
        self.assertIn("    demo_state_in: list[float] | None = None\n", python)
        self.assertIn('REQUIRED_OUTPUT_NAMES = ("demo_limit_seconds", )', python)

    def test_registered_name_and_check_name(self):
        from mlmodels._signature import check_name, registered_name

        self.assertEqual("rackmains_ups_battery", registered_name("rackmains", "ups", "battery"))
        self.assertEqual("example_static_constant", registered_name("example", "static", "constant"))
        with self.assertRaises(ValueError):
            check_name("Bad-Name")


class AuthoringLoadTest(unittest.TestCase):
    def test_a_candidate_integer_output_is_truncated_while_the_shipped_loader_refuses_it(self):
        from mlmodels._replay import load_model
        from mlmodels._signature import build_signature, signature_input, signature_output
        from mlmodels.runtime.loader import ModelError, load_static

        signature = build_signature("demo_calc", [signature_input("demo_in", "none", "A number.")], [signature_output("demo_out", "none", "A count.", datatype="INT64")])
        self.assertEqual({"demo_out": [125]}, load_model("", "static", signature, {"demo_out": 125.7})({"demo_in": [1.0]}))
        from mlmodels.runtime.loader import Model, Project

        strict = Model("", Project({"name": "demo_calc", "flavour": "static"}, json.dumps(signature), ""), load_static(json.dumps({"demo_out": 125.7}), json.dumps(signature)))
        with self.assertRaises(ModelError):
            strict.predict({"demo_in": [1.0]})


class LoaderTest(unittest.TestCase):
    def test_a_project_loads_and_verifies_for_every_flavour(self):
        from mlmodels.runtime.loader import load

        static = join(ROOT, "rue/mlmodels/src/main/notebook/example/static/constant/project")
        for flavour, directory in (("pyfunc", build_project("pyfunc")), ("wasm", build_project("wasm")), ("onnx", build_project("onnx")), ("static", static)):
            model = load(directory)
            model.verify()
            self.assertEqual(flavour, model.info().flavour)

    def test_a_malformed_project_is_a_load_error_and_never_another_exception(self):
        from mlmodels.runtime.loader import ModelError, load

        def damaged(change):
            directory = build_project("wasm")
            change(directory)
            return directory

        def truncate(directory):
            with open(join(directory, "project.json"), "r+") as file:
                file.truncate(10)

        def append(directory):
            with open(join(directory, "model.wasm"), "ab") as file:
                file.write(b"\0")

        def delete(name):
            return lambda directory: os.remove(join(directory, name))

        for change in (truncate, append, delete("model.wasm"), delete("signature.json"), delete("evaluation.json"), delete("project.json")):
            with self.assertRaises(ModelError) as raised:
                load(damaged(change))
            self.assertEqual("Load", raised.exception.kind)

    def test_a_request_missing_a_required_input_is_a_signature_error(self):
        from mlmodels.runtime.loader import ModelError, load

        with self.assertRaises(ModelError) as raised:
            load(build_project("wasm")).predict({})
        self.assertEqual("Signature", raised.exception.kind)

    def test_an_integer_output_that_is_not_an_integer_is_a_runtime_error(self):
        from mlmodels.runtime.loader import Model, ModelError, Project

        signature = {"inputs": [], "outputs": [{"name": "y", "datatype": "INT64", "shape": [1]}], "parameters": {}}
        for bad in (float("nan"), 1.5, 2.0**60):
            model = Model("", Project({"name": "demo", "flavour": "static"}, json.dumps(signature), ""), lambda _inputs, bad=bad: {"y": [bad]})
            with self.assertRaises(ModelError) as raised:
                model.predict({})
            self.assertEqual("Runtime", raised.exception.kind)
        self.assertEqual({"y": [3]}, Model("", Project({"name": "demo", "flavour": "static"}, json.dumps(signature), ""), lambda _inputs: {"y": [3.0]}).predict({}))

    def test_a_golden_difference_is_a_verify_error(self):
        from mlmodels.runtime.loader import ModelError, load

        with self.assertRaises(ModelError) as raised:
            load(build_project("wasm", golden_out=9.5)).verify()
        self.assertEqual("Verify", raised.exception.kind)


class EmbedLoaderTest(unittest.TestCase):
    def test_the_loader_is_written_once_and_a_repeat_writes_nothing(self):
        from mlmodels._embed import embed_loader

        consumer = join(tempfile.mkdtemp(), "mlserver")
        self.assertEqual(["loader.py", "__init__.py", "vocabulary.py"], embed_loader(consumer, "python"))
        self.assertEqual([], embed_loader(consumer, "python"))
        with open(join(consumer, "src/main/python/serving/model/loader.py")) as written, open(join(ROOT, "rue/mlmodels/src/main/python/mlmodels/runtime/loader.py")) as source:
            self.assertTrue(written.read().endswith(source.read()))
        with open(join(consumer, "src/main/python/serving/model/loader.py"), "a") as written:
            written.write("#")
        self.assertEqual(["loader.py"], embed_loader(consumer, "python"))

    def test_a_language_without_a_loader_is_refused(self):
        from mlmodels._embed import embed_loader

        with self.assertRaises(ValueError):
            embed_loader(tempfile.mkdtemp(), "cobol")


class ReplayTest(unittest.TestCase):
    def test_each_flavour_replays_its_golden_exactly(self):
        from mlmodels._replay import replay_project

        for flavour in ("pyfunc", "wasm", "onnx"):
            self.assertEqual([], replay_project(build_project(flavour)), flavour)

    def test_a_response_that_differs_from_the_golden_is_a_finding(self):
        from mlmodels._replay import replay_project

        for flavour in ("pyfunc", "wasm", "onnx"):
            self.assertEqual(["RP003"], [rule for rule, _ in replay_project(build_project(flavour, golden_out=3.5))], flavour)

    def test_a_stated_tolerance_accepts_a_small_difference_and_rejects_a_large_one(self):
        from mlmodels._replay import replay_project

        bounds = {"demo_out": {"absolute": 1e-3}}
        for flavour in ("pyfunc", "wasm", "onnx"):
            self.assertEqual([], replay_project(build_project(flavour, golden_out=3.0000001, tolerance=bounds)), flavour)
            self.assertEqual(["RP003"], [rule for rule, _ in replay_project(build_project(flavour, golden_out=3.5, tolerance=bounds))], flavour)
            self.assertEqual(["RP003"], [rule for rule, _ in replay_project(build_project(flavour, golden_out=3.0000001))], flavour)

    def test_a_relative_tolerance_scales_with_the_expected_value(self):
        from mlmodels._replay import replay_project

        self.assertEqual([], replay_project(build_project("pyfunc", golden_out=3.003, tolerance={"demo_out": {"relative": 0.002}})))
        self.assertEqual(["RP003"], [rule for rule, _ in replay_project(build_project("pyfunc", golden_out=3.01, tolerance={"demo_out": {"relative": 0.002}}))])

    def test_a_malformed_tolerance_is_a_finding(self):
        for bounds in ({"demo_other": {"absolute": 1}}, {"demo_out": {"absolute": -1}}, {"demo_out": {}}, {"demo_out": {"scale": 1}}, {"demo_out": {"absolute": True}}):
            with self.assertRaises(ValueError) as refused:
                build_project("pyfunc", tolerance=bounds)
            self.assertIn("PJ015", str(refused.exception), bounds)


class MetadataTest(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.mkdtemp()
        os.makedirs(join(self.workspace, "data", "training", "2026-01-01_00-00-00"))
        with open(join(self.workspace, "data", "training", "2026-01-01_00-00-00", "a.csv"), "w") as data_file:
            data_file.write("x\n1\n")
        self.write_notebook(["x = 1\n"], ["# a heading\n"])
        self.project_dir = build_project("wasm", signature_version=1000)

    def write_notebook(self, code, markdown):
        with open(join(self.workspace, "notebook.ipynb"), "w") as notebook_file:
            json.dump({"cells": [{"cell_type": "code", "source": code}, {"cell_type": "markdown", "source": markdown}]}, notebook_file)

    def metadata(self, **changes):
        from mlmodels._metadata import METADATA_SCHEMA, content_sha256

        return {
            "schema": METADATA_SCHEMA,
            "version": None,
            "content_sha256": content_sha256(self.project_dir),
            "inputs_sha256": "a" * 64,
            "target": {"kind": "embedded", "language": "go"},
            "release": None,
            **changes,
        }

    def place(self, metadata):
        from mlmodels._metadata import PROJECT_DIR, write_metadata

        shutil.copytree(self.project_dir, join(self.workspace, PROJECT_DIR), dirs_exist_ok=True)
        write_metadata(self.workspace, metadata)
        self.write_requirements(metadata)

    def write_requirements(self, metadata):
        from mlmodels._metadata import REQUIREMENT_FILES, derived_requirements, read_runtime

        derived = derived_requirements(read_runtime(self.workspace), "wasm", metadata["target"])
        for language, file_name in REQUIREMENT_FILES.items():
            path = join(self.workspace, file_name)
            if language in derived:
                with open(path, "w") as requirements_file:
                    requirements_file.write("".join(f"{name}\n" for name in derived[language]))
            elif os.path.exists(path):
                os.remove(path)

    def rules(self):
        from mlmodels._metadata import lint_metadata

        return sorted({rule for rule, _ in lint_metadata(self.workspace, "wasm")})

    def test_a_consistent_workspace_has_no_findings(self):
        self.place(self.metadata())
        self.assertEqual([], self.rules())

    def test_a_missing_metadata_or_field_or_project_is_a_finding(self):
        self.assertEqual(["MD001"], self.rules())
        self.place(self.metadata())
        shutil.rmtree(join(self.workspace, "project"))
        self.assertEqual(["MD003"], self.rules())
        from mlmodels._metadata import METADATA_SCHEMA, write_metadata

        write_metadata(self.workspace, {"schema": METADATA_SCHEMA})
        self.assertEqual(["MD002"], self.rules())
        write_metadata(self.workspace, {"schema": METADATA_SCHEMA - 1})
        self.assertEqual(["MD001"], self.rules())

    def test_a_python_dependency_with_no_pin_is_a_finding(self):
        from mlmodels._metadata import lint_metadata

        with open(join(self.project_dir, "project.json")) as manifest_file:
            manifest = json.load(manifest_file)
        with open(join(self.project_dir, "project.json"), "w") as manifest_file:
            json.dump({**manifest, "runtime": {"python": ["polars"]}}, manifest_file)
        self.place(self.metadata(target={"kind": "served"}))
        pins_path = join(self.workspace, "pins.txt")
        with open(pins_path, "w") as pins_file:
            pins_file.write("numpy==2.0.0\n")
        self.assertEqual(["MD005"], sorted({rule for rule, _ in lint_metadata(self.workspace, "wasm", pins_path)}))
        with open(pins_path, "a") as pins_file:
            pins_file.write("Polars==2.1.0\n")
        self.assertEqual([], lint_metadata(self.workspace, "wasm", pins_path))

    def test_a_workspace_signature_that_differs_from_the_project_signature_is_a_finding(self):
        self.place(self.metadata())
        project_signature = join(self.workspace, "project", "signature.json")
        shutil.copy(project_signature, join(self.workspace, "signature.json"))
        self.assertEqual([], self.rules())
        with open(join(self.workspace, "signature.json")) as signature_file:
            signature = json.load(signature_file)
        signature["outputs"][0]["name"] = "renamed_output"
        with open(join(self.workspace, "signature.json"), "w") as signature_file:
            json.dump(signature, signature_file)
        self.assertEqual(["MD003"], self.rules())

    def test_load_signature_and_signature_names_read_the_workspace_signature(self):
        from mlmodels._workspace import load_signature, signature_names

        self.place(self.metadata())
        shutil.copy(join(self.workspace, "project", "signature.json"), join(self.workspace, "signature.json"))
        signature = load_signature(basename(self.workspace), notebook_dir=dirname(self.workspace))
        inputs, outputs = signature_names(signature)
        self.assertEqual([entry["name"] for entry in signature["inputs"]], inputs)
        self.assertEqual([entry["name"] for entry in signature["outputs"]], outputs)
        self.assertTrue(inputs and outputs)

    def test_a_requirements_file_that_differs_from_the_derived_names_is_a_finding(self):
        from mlmodels._metadata import LOCAL_TARGET, REQUIREMENT_FILES

        self.place(self.metadata(target={"kind": "served"}))
        self.assertEqual([], self.rules())
        path = join(self.workspace, REQUIREMENT_FILES["python"])
        with open(path, "w") as requirements_file:
            requirements_file.write("wasmtime\npolars\n")
        self.assertEqual(["MD005"], self.rules())
        os.remove(path)
        self.assertEqual(["MD005"], self.rules())
        self.place(self.metadata(target=LOCAL_TARGET))
        self.assertEqual([], self.rules())
        with open(path, "w") as requirements_file:
            requirements_file.write("wasmtime\n")
        self.assertEqual(["MD005"], self.rules())

    def test_requirements_report_an_unpinned_python_name_and_what_an_embedded_host_lacks(self):
        from mlmodels._metadata import requirements

        with open(join(self.project_dir, "project.json")) as manifest_file:
            manifest = json.load(manifest_file)
        with open(join(self.project_dir, "project.json"), "w") as manifest_file:
            json.dump({**manifest, "runtime": {"python": ["polars"], "wasm": ["tanh"]}}, manifest_file)
        module = self.workspace.rstrip("/").split("/")[-3]
        pins_path = join(self.workspace, "pins.txt")
        source_dir = join(self.workspace, "source", "..", "source")
        go_dir = join(self.workspace, "source", "host", module, "src", "main", "go", module)
        os.makedirs(go_dir)
        with open(pins_path, "w") as pins_file:
            pins_file.write("wasmtime==1.0.0\n")
        with open(join(go_dir, "go.mod"), "w") as go_file:
            go_file.write("module host\n")
        self.place(self.metadata(target={"kind": "served"}))
        to_add, summary, lines = requirements(self.workspace, "wasm", pins_path, source_dir)
        self.assertEqual((0, "python polars"), (to_add, summary))
        self.assertTrue(any(line.startswith("! polars has no project wide pin") for line in lines))
        with open(pins_path, "a") as pins_file:
            pins_file.write("polars==2.0.0\n")
        self.assertEqual((0, "", []), requirements(self.workspace, "wasm", pins_path, source_dir))
        self.place(self.metadata(target={"kind": "embedded", "language": "go"}))
        to_add, summary, lines = requirements(self.workspace, "wasm", pins_path, source_dir)
        self.assertEqual((1, "go wazero"), (to_add, summary))
        self.assertIn("  + wazero", lines)
        with open(join(go_dir, "go.mod"), "a") as go_file:
            go_file.write("require github.com/tetratelabs/wazero v1.0.0\n")
        self.assertEqual((0, "", []), requirements(self.workspace, "wasm", pins_path, source_dir))

    def test_the_changed_command_reports_a_notebook_that_packages_nothing(self):
        import contextlib
        import io

        from mlmodels._command import main

        pins_path = join(self.workspace, "py_deps.txt")
        with open(pins_path, "w") as pins_file:
            pins_file.write("numpy==2.0.0\n")

        def state():
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                main(["changed", self.workspace, pins_path])
            return output.getvalue().strip()

        self.assertEqual("unpackaged", state())
        self.write_notebook(["manifest = package_model(ws, 1000, golden)\n"], ["# a heading\n"])
        self.assertEqual("changed", state())

    def test_a_project_that_differs_from_its_hash_is_a_finding(self):
        self.place(self.metadata(content_sha256="b" * 64))
        self.assertEqual(["MD003"], self.rules())

    def test_every_target_carries_a_valid_signature_version(self):
        embedded = {"kind": "embedded", "language": "go"}
        with open(join(self.project_dir, "signature.json")) as signature_file:
            signature = {key: value for key, value in json.load(signature_file).items() if key != "signature_version"}
        for target, fields, flagged in (
            ({"kind": "served"}, {}, True),
            ({"kind": "served"}, {"signature_version": 999}, True),
            ({"kind": "served"}, {"signature_version": True}, True),
            ({"kind": "served"}, {"signature_version": "1000"}, True),
            ({"kind": "served"}, {"signature_version": 1000}, False),
            (embedded, {"signature_version": 1000}, False),
            (embedded, {}, True),
            ({"kind": "local"}, {"signature_version": 1001}, False),
            ({"kind": "local"}, {}, True),
        ):
            with self.subTest(target=target["kind"], fields=fields):
                self.place(self.metadata(target=target))
                with open(join(self.workspace, "signature.json"), "w") as signature_file:
                    json.dump({**signature, **fields}, signature_file)
                self.assertEqual(flagged, "MD006" in self.rules())

    def test_a_baseline_is_an_object_on_a_served_target_only(self):
        with open(join(self.project_dir, "signature.json")) as signature_file:
            signature = json.load(signature_file)
        for target, baseline, flagged in (
            ({"kind": "served"}, signature, False),
            ({"kind": "served"}, "text", True),
            ({"kind": "embedded", "language": "go"}, signature, True),
        ):
            with self.subTest(target=target["kind"], baseline=type(baseline).__name__):
                self.place(self.metadata(target=target, baseline=baseline))
                with open(join(self.workspace, "signature.json"), "w") as signature_file:
                    json.dump({**signature, **({"signature_version": 1000} if target["kind"] == "served" else {})}, signature_file)
                self.assertEqual(flagged, "MD006" in self.rules())

    def test_a_target_with_no_wrapper_for_its_flavour_is_a_finding(self):
        self.place(self.metadata(target={"kind": "embedded", "language": "java"}))
        self.assertEqual(["MD004"], self.rules())
        self.place(self.metadata(target={"kind": "embedded", "language": "go"}))
        self.assertEqual([], self.rules())

    def test_an_unreleased_project_has_a_snapshot_version_or_none_and_a_released_one_a_release_version(self):
        release = {"timestamp": "2026-11-07T10:42:11Z", "signature": {}}
        self.place(self.metadata(version="10.200.1951-SNAPSHOT"))
        self.assertEqual([], self.rules())
        self.place(self.metadata(version=None))
        self.assertEqual([], self.rules())
        self.place(self.metadata(version="10.200.1951"))
        self.assertEqual(["MD002"], self.rules())
        self.place(self.metadata(version="10.200.1949", release=release))
        self.assertEqual([], self.rules())
        self.place(self.metadata(version="1000", release=release))
        self.assertEqual(["MD002"], self.rules())
        self.place(self.metadata(version="10.200.1951-SNAPSHOT", release=release))
        self.assertEqual(["MD002"], self.rules())
        self.place(self.metadata(version="10.200.1949", release={"timestamp": "2026-11-07T10:42:11Z"}))
        self.assertEqual(["MD002"], self.rules())

    def test_the_inputs_hash_moves_with_code_data_and_pins_but_not_with_markdown(self):
        from mlmodels._metadata import inputs_sha256

        pins = {"numpy": "2.0"}
        before = inputs_sha256(self.workspace, pins)
        self.write_notebook(["x = 1\n"], ["# another heading\n"])
        self.assertEqual(before, inputs_sha256(self.workspace, pins))
        self.write_notebook(["x = 2\n"], ["# a heading\n"])
        self.assertNotEqual(before, inputs_sha256(self.workspace, pins))
        self.write_notebook(["x = 1\n"], ["# a heading\n"])
        self.assertNotEqual(before, inputs_sha256(self.workspace, {"numpy": "2.1"}))
        with open(join(self.workspace, "data", "training", "2026-01-01_00-00-00", "a.csv"), "a") as data_file:
            data_file.write("2\n")
        self.assertNotEqual(before, inputs_sha256(self.workspace, pins))

    def test_the_inputs_hash_ignores_a_live_run_and_follows_a_frozen_one(self):
        from mlmodels._metadata import inputs_sha256

        directory = join(self.workspace, "data", "1000")
        os.makedirs(directory)
        for live in (True, False):
            with open(join(directory, "a.json"), "w") as sidecar_file:
                json.dump({"live": live}, sidecar_file)
            with open(join(directory, "a.csv"), "w") as data_file:
                data_file.write("x\n1\n")
            before = inputs_sha256(self.workspace, {})
            with open(join(directory, "a.csv"), "a") as data_file:
                data_file.write("2\n")
            self.assertEqual(live, before == inputs_sha256(self.workspace, {}))

    def test_the_pins_are_read_for_the_named_runtime_packages_only(self):
        from mlmodels._metadata import read_pins

        path = join(tempfile.mkdtemp(), "py_deps_prod.txt")
        with open(path, "w") as pins_file:
            pins_file.write("numpy==2.5.4\nruff==0.17.3\nwasmtime==50.0.1\n# comment\n")
        self.assertEqual({"numpy": "2.5.4", "wasmtime": "50.0.1"}, read_pins(path))


class ReleaseTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(contextlib.chdir(fresh_mlruns_dir()))
        from mlmodels._release import NOTEBOOK_ROOT

        self.TARGET = {"kind": "served"}

        self.source = tempfile.mkdtemp()
        self.workspace = join(self.source, NOTEBOOK_ROOT, "demo", "replay", "double")
        os.makedirs(join(self.workspace, "data"))
        with open(join(self.workspace, "notebook.ipynb"), "w") as notebook_file:
            json.dump({"cells": [{"cell_type": "code", "source": ["x = 1\n"]}]}, notebook_file)
        self.pins = join(tempfile.mkdtemp(), "pins.txt")
        with open(self.pins, "w") as pins_file:
            pins_file.write("numpy==2.0\n")
        self.consumer = join(self.source, "max", "consumer")
        self.slot = join(self.consumer, "src", "build", "resources", "model", "double")
        os.makedirs(dirname(self.slot))
        shutil.copytree(build_project("wasm", golden_out=3.5), self.slot)

    def record(self, project_dir=None, target=None):
        from mlmodels._metadata import record_project

        return record_project(self.workspace, project_dir or build_project("wasm"), self.TARGET if target is None else target, self.pins)

    def version_file(self, text):
        path = join(tempfile.mkdtemp(), ".version")
        with open(path, "w") as version_file:
            version_file.write(text)
        return path

    def release(self, version="10.200.1", **options):
        from mlmodels._release import release_workspaces

        return release_workspaces(self.source, version, **options)

    def test_a_project_is_recorded_and_a_workspace_with_no_target_is_not(self):
        from mlmodels._metadata import METADATA_FILE

        recorded = self.record()
        assert recorded is not None
        self.assertEqual("served", recorded["target"]["kind"])
        self.assertTrue(os.path.isfile(join(self.workspace, METADATA_FILE)))
        os.remove(join(self.workspace, METADATA_FILE))
        self.assertIsNone(self.record(target={}))
        self.assertFalse(os.path.isfile(join(self.workspace, METADATA_FILE)))

    def test_setup_workspace_prints_the_recorded_metadata_of_the_workspace(self):
        import contextlib
        import io

        from mlmodels.workflow.setup import setup_workspace

        self.record(target={"kind": "embedded", "language": "go"})
        shutil.copy(join(self.workspace, "project", "signature.json"), join(self.workspace, "signature.json"))
        notebook_dir = tempfile.mkdtemp()
        shutil.copytree(self.workspace, join(notebook_dir, "demo", "calc", "run"))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            ws = setup_workspace("demo/calc/run", notebook_dir)
        printed = output.getvalue()
        self.assertTrue(ws.env["MLFLOW_TRACKING_URI"].startswith("http"))
        self.assertEqual("demo_calc_run", ws.model_name)
        for expected in ("Target    embedded go", "Requires  []", "Inputs    ", "Outputs   "):
            self.assertIn(expected, printed)

    def test_every_json_document_starts_with_its_schema(self):
        from mlmodels._lint_project import lint_project
        from mlmodels._metadata import METADATA_FILE

        self.record()
        for path in (join(self.workspace, METADATA_FILE), *(join(self.workspace, "project", name) for name in ("project.json", "signature.json", "golden.json"))):
            with open(path) as document_file:
                self.assertEqual("schema", next(iter(json.load(document_file))), path)
        golden_path = join(self.workspace, "project", "golden.json")
        with open(golden_path) as golden_file:
            golden = json.load(golden_file)
        with open(golden_path, "w") as golden_file:
            json.dump({"sequences": golden["sequences"], "schema": golden["schema"]}, golden_file)
        self.assertIn("PJ001", {rule for rule, _ in lint_project(join(self.workspace, "project"))})

    def test_a_workspace_whose_project_is_not_checked_out_cannot_be_released(self):
        from mlmodels._errors import GateError

        self.record()
        shutil.rmtree(join(self.workspace, "project"))
        with self.assertRaises(GateError):
            self.release()

    def test_a_local_project_is_recorded_and_never_released(self):
        from mlmodels._metadata import LOCAL_TARGET, lint_metadata, read_metadata

        recorded = self.record(target=LOCAL_TARGET)
        assert recorded is not None
        self.assertEqual(LOCAL_TARGET, recorded["target"])
        self.assertEqual([], lint_metadata(self.workspace, "wasm"))
        self.assertEqual([], self.release())
        self.assertIsNone(read_metadata(self.workspace)["release"])

    def test_a_recorded_project_writes_the_python_requirements_of_its_target_and_removes_them_for_another_language(self):
        from mlmodels._metadata import LOCAL_TARGET, REQUIREMENT_FILES

        self.record(target={"kind": "served"})
        with open(join(self.workspace, REQUIREMENT_FILES["python"])) as python_file:
            self.assertEqual("wasmtime\n", python_file.read())
        self.record(target={"kind": "embedded", "language": "go"})
        self.assertFalse(os.path.exists(join(self.workspace, REQUIREMENT_FILES["python"])))
        self.record(target={"kind": "served"})
        self.record(target=LOCAL_TARGET)
        self.assertEqual([], [name for name in REQUIREMENT_FILES.values() if os.path.exists(join(self.workspace, name))])

    def test_a_runtime_with_no_pin_is_refused_before_the_workspace_changes(self):
        from mlmodels._errors import GateError

        project_dir = build_project("wasm")
        with open(join(project_dir, "project.json")) as manifest_file:
            manifest = json.load(manifest_file)
        manifest["runtime"] = {"python": ["unpinned_package"]}
        with open(join(project_dir, "project.json"), "w") as manifest_file:
            json.dump(manifest, manifest_file)
        with self.assertRaises(GateError):
            self.record(project_dir)
        self.assertFalse(os.path.exists(join(self.workspace, "project")))

    def test_the_image_pins_are_the_consumer_base_plus_the_declared_runtime_and_an_unpinned_one_is_refused(self):
        import io

        from mlmodels._command import main

        self.record()
        manifest_path = join(self.workspace, "project", "project.json")
        with open(manifest_path) as manifest_file:
            manifest = json.load(manifest_file)

        def declare(runtime):
            with open(manifest_path, "w") as manifest_file:
                json.dump({**manifest, "runtime": runtime}, manifest_file)

        declare({"python": ["numpy"]})
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            self.assertEqual(0, main(["docker-args", self.source, self.pins]))
        self.assertEqual('--build-arg "PINS=numpy==2.0"', printed.getvalue().strip())
        declare({"python": ["scikit-learn"]})
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(1, main(["docker-args", self.source, self.pins]))
        self.assertEqual("", printed.getvalue())

    def test_a_release_keeps_the_version_while_content_is_unchanged(self):
        from mlmodels._metadata import read_metadata

        self.record()
        self.assertEqual(["demo_replay_double"], self.release())
        self.assertEqual(("10.200.1", True), (read_metadata(self.workspace)["version"], read_metadata(self.workspace)["release"] is not None))
        self.record()
        self.release("10.200.2")
        self.assertEqual("10.200.1", read_metadata(self.workspace)["version"])
        self.record(project_dir=build_project("wasm", golden_out=3.5))
        self.assertIsNone(read_metadata(self.workspace)["release"])

    def test_an_unreleased_project_carries_the_snapshot_until_its_content_changes_or_it_is_released(self):
        from mlmodels._metadata import read_metadata, record_project

        def record(project_dir, version):
            recorded = record_project(self.workspace, project_dir, self.TARGET, self.pins, self.version_file(version))
            assert recorded is not None
            return recorded

        self.assertEqual("10.200.1951-SNAPSHOT", record(build_project("wasm"), "10.200.1951-SNAPSHOT\n")["version"])
        self.assertEqual("10.200.1951-SNAPSHOT", record(build_project("wasm"), "10.200.1952-SNAPSHOT")["version"])
        self.assertEqual("10.200.1952-SNAPSHOT", record(build_project("wasm", golden_out=3.5), "10.200.1952-SNAPSHOT")["version"])
        self.assertEqual("10.200.1952-SNAPSHOT", record(build_project("wasm", golden_out=3.5), "10.200.1953")["version"])
        self.assertIsNone(record(build_project("wasm", golden_out=4.5), "10.200.1953")["version"])
        record(build_project("wasm"), "10.200.1954-SNAPSHOT")
        self.release()
        self.assertEqual("10.200.1", read_metadata(self.workspace)["version"])
        self.assertEqual("10.200.1", record(build_project("wasm"), "10.200.1955-SNAPSHOT")["version"])

    def test_the_fixtures_module_is_never_released(self):
        from mlmodels._release import NOTEBOOK_ROOT

        fixture = join(self.source, NOTEBOOK_ROOT, "example", "replay", "double")
        os.makedirs(join(fixture, "data"))
        shutil.copy(join(self.workspace, "notebook.ipynb"), fixture)
        from mlmodels._metadata import record_project

        record_project(fixture, build_project("wasm"), self.TARGET, self.pins)
        self.assertEqual([], self.release())

    def test_a_consumer_embeds_the_released_project_and_is_stale_until_it_does(self):
        from mlmodels._embed import embed_consumer, stale_consumers
        from mlmodels._release import slot_findings

        self.record()
        self.assertEqual("none", embed_consumer(self.consumer, self.source, "demo_replay_double"))
        self.release()
        self.assertEqual([self.consumer], stale_consumers(self.source))
        self.assertEqual("embedded", embed_consumer(self.consumer, self.source, "demo_replay_double"))
        self.assertEqual(("unchanged", []), (embed_consumer(self.consumer, self.source, "demo_replay_double"), stale_consumers(self.source)))
        self.assertEqual([], slot_findings(self.slot, self.source))
        with open(join(self.slot, "project.json"), "a") as manifest_file:
            manifest_file.write(" ")
        self.assertEqual(["CP004"], [rule for rule, _ in slot_findings(self.slot, self.source)])
        self.assertEqual("embedded", embed_consumer(self.consumer, self.source, "demo_replay_double"))

    def test_a_python_consumer_gets_a_loader_root_and_model_file_that_load_and_replay(self):
        import importlib

        from mlmodels._embed import embed_consumer, loader_findings, stale_consumers

        self.record(target={"kind": "embedded", "language": "python"})
        self.release()
        self.assertEqual([self.consumer], stale_consumers(self.source))
        self.assertEqual("embedded", embed_consumer(self.consumer, self.source, "demo_replay_double"))
        self.assertEqual(("unchanged", [], []), (embed_consumer(self.consumer, self.source, "demo_replay_double"), stale_consumers(self.source), loader_findings(self.consumer, self.source)))
        package = join(self.consumer, "src/main/python/consumer/model")
        self.assertEqual(["__init__.py", "double.py", "loader.py"], sorted(os.listdir(package)))
        sys.path.insert(0, join(self.consumer, "src/main/python"))
        self.addCleanup(sys.path.remove, join(self.consumer, "src/main/python"))
        self.addCleanup(lambda: [sys.modules.pop(name) for name in [name for name in sys.modules if name == "consumer" or name.startswith("consumer.")]])
        generated = importlib.import_module("consumer.model.double")
        model = generated.load(self.slot)
        model.verify()
        response = generated.Response.from_tensors(model.predict(generated.Request(demo_in=1.5).to_tensors()))
        self.assertEqual(generated.Response(demo_out=3.0), response)
        with self.assertRaises(generated.loader.ModelError):
            generated.Response.from_tensors({})
        with open(join(package, "double.py"), "a") as model_file:
            model_file.write("# edited\n")
        self.assertEqual([], loader_findings(self.consumer, self.source))
        with open(join(package, "loader.py"), "a") as loader_file:
            loader_file.write("#")
        self.assertEqual(["CP005"], [rule for rule, _ in loader_findings(self.consumer, self.source)])
        self.assertEqual("embedded", embed_consumer(self.consumer, self.source, "demo_replay_double"))
        self.assertEqual([], loader_findings(self.consumer, self.source))

    def test_a_language_with_no_embedding_is_refused_before_the_slot_is_touched(self):
        from mlmodels._embed import embed_consumer
        from mlmodels._errors import GateError
        from mlmodels._metadata import content_sha256

        self.record(target={"kind": "embedded", "language": "java"})
        self.release()
        before = content_sha256(self.slot)
        with self.assertRaises(GateError):
            embed_consumer(self.consumer, self.source, "demo_replay_double")
        self.assertEqual(before, content_sha256(self.slot))

    def test_a_rust_consumer_gets_a_loader_root_and_model_file_that_compile_and_replay(self):
        import unittest.mock

        from mlmodels._embed import embed_consumer, loader_findings
        from mlmodels._errors import GateError

        home = os.path.expanduser("~/.rust/versions/asystem")
        env = {"CARGO_HOME": home, "RUSTUP_HOME": home, "PATH": f"{home}/bin:{os.environ['PATH']}", "CARGO_TARGET_DIR": join(ROOT, "rue/mlmodels/target/rust-embed")}
        crate = join(self.consumer, "src/main/rust/consumer")
        os.makedirs(join(crate, "src"))
        reference = join(ROOT, "rue/mlmodels/src/main/rust/mlmodels")
        with open(join(reference, "Cargo.toml")) as cargo_file:
            cargo = "".join(line for line in cargo_file if not line.startswith("ureq")).replace('name = "consumer"', 'name = "embedded"')
        with open(join(crate, "Cargo.toml"), "w") as cargo_file:
            cargo_file.write(cargo)
        shutil.copy(join(reference, "Cargo.lock"), crate)
        with open(join(crate, "src/lib.rs"), "w") as lib_file:
            lib_file.write(
                "pub mod model;\n\n#[cfg(test)]\nmod tests {\n    use std::path::Path;\n\n    use crate::model::double::{load, Request, Response};\n\n"
                '    #[test]\n    fn the_embedded_model_replays_and_converts() {\n        let model = load(Path::new(&std::env::var("PROJECT_DIR").unwrap())).unwrap();\n'
                "        model.verify().unwrap();\n        let response = Response::try_from(model.predict(&Request { demo_in: 1.5 }.into()).unwrap()).unwrap();\n"
                "        assert_eq!(Response { demo_out: 3.0 }, response);\n    }\n}\n"
            )
        self.record(target={"kind": "embedded", "language": "rust"})
        self.release()
        with unittest.mock.patch.dict(os.environ, env):
            self.assertEqual("embedded", embed_consumer(self.consumer, self.source, "demo_replay_double"))
            self.assertEqual("unchanged", embed_consumer(self.consumer, self.source, "demo_replay_double"))
            completed = subprocess.run(["cargo", "test", "--offline", "--quiet"], cwd=crate, env={**os.environ, "PROJECT_DIR": self.slot}, capture_output=True, text=True, timeout=900, check=False)
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            self.assertEqual([], loader_findings(self.consumer, self.source))
            with open(join(crate, "src/model/loader.rs"), "a") as loader_file:
                loader_file.write("// edit\n")
            self.assertEqual(["CP005"], [rule for rule, _ in loader_findings(self.consumer, self.source)])
            with open(join(crate, "src/model/double.rs")) as model_file:
                original = model_file.read()
            with open(join(crate, "src/model/double.rs"), "w") as model_file:
                model_file.write(original.replace("project demo_replay_double", "project another_double"))
            self.assertIn("CP005", [rule for rule, _ in loader_findings(self.consumer, self.source)])
            self.assertEqual("embedded", embed_consumer(self.consumer, self.source, "demo_replay_double"))
            with open(join(crate, "src/model/double.rs")) as model_file:
                self.assertEqual(original, model_file.read())
            with open(join(crate, "src/model/old_double.rs"), "w") as model_file:
                model_file.write("// a model file from an earlier version\n")
            self.assertEqual(["CP006"], [rule for rule, _ in loader_findings(self.consumer, self.source)])
            self.assertEqual("embedded", embed_consumer(self.consumer, self.source, "demo_replay_double"))
            self.assertEqual(["double.rs", "loader.rs", "mod.rs"], sorted(os.listdir(join(crate, "src/model"))))
            self.assertEqual([], loader_findings(self.consumer, self.source))
            with open(join(self.slot, "project.json")) as manifest_file:
                manifest = json.load(manifest_file)
            manifest["name"] = "another_double"
            with open(join(self.slot, "project.json"), "w") as manifest_file:
                json.dump(manifest, manifest_file)
            with self.assertRaises(GateError):
                embed_consumer(self.consumer, self.source, "demo_replay_double")
            manifest["name"] = "demo_replay_double"
            with open(join(self.slot, "project.json"), "w") as manifest_file:
                json.dump(manifest, manifest_file)
            with open(join(crate, "Cargo.toml"), "w") as cargo_file:
                cargo_file.write(cargo.replace('sha2 = "0.11.1"', 'sha2 = "0.10"'))
            with self.assertRaises(GateError) as raised:
                embed_consumer(self.consumer, self.source, "demo_replay_double")
            self.assertIn("sha2", raised.exception.cause)

    def test_a_go_consumer_gets_a_loader_and_a_model_package_that_compile_and_replay(self):
        import unittest.mock

        from mlmodels._embed import embed_consumer
        from mlmodels._errors import GateError

        goroot = os.path.expanduser("~/.goenv/versions/1.27.0")
        env = {"GOROOT": goroot, "GOPATH": join(ROOT, "../.go"), "PATH": f"{goroot}/bin:{os.environ['PATH']}", "GOFLAGS": "-mod=mod", "GOPROXY": "off"}
        crate = join(self.consumer, "src/main/go/consumer")
        os.makedirs(crate)
        reference = join(ROOT, "rue/mlmodels/src/main/go/mlmodels")
        with open(join(reference, "go.mod")) as mod_file:
            mod = mod_file.read().replace("module consumer", "module embedded")
        with open(join(crate, "go.mod"), "w") as mod_file:
            mod_file.write(mod)
        shutil.copy(join(reference, "go.sum"), crate)
        self.record(target={"kind": "embedded", "language": "go"})
        self.release()
        with unittest.mock.patch.dict(os.environ, env):
            self.assertEqual("embedded", embed_consumer(self.consumer, self.source, "demo_replay_double"))
            self.assertEqual("unchanged", embed_consumer(self.consumer, self.source, "demo_replay_double"))
            with open(join(crate, "model/double/double_test.go"), "w") as test_file:
                test_file.write(
                    'package double\n\nimport (\n\t"os"\n\t"testing"\n)\n\nfunc TestEmbedded(t *testing.T) {\n\tmodel, err := Load(os.Getenv("PROJECT_DIR"))\n\tif err != nil {\n\t\tt.Fatal(err)\n\t}\n'
                    "\tif err := model.Verify(); err != nil {\n\t\tt.Fatal(err)\n\t}\n\toutputs, err := model.Predict(Request{DemoIn: 1.5}.ToTensors())\n\tif err != nil {\n\t\tt.Fatal(err)\n\t}\n"
                    '\tresponse, err := FromTensors(outputs)\n\tif err != nil || response.DemoOut != 3 {\n\t\tt.Fatalf("got %v %v", response, err)\n\t}\n}\n'
                )
            completed = subprocess.run(["go", "test", "./..."], cwd=crate, env={**os.environ, "PROJECT_DIR": self.slot}, capture_output=True, text=True, timeout=900, check=False)
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            vetted = subprocess.run(["go", "vet", "./..."], cwd=crate, capture_output=True, text=True, timeout=300, check=False)
            self.assertEqual(0, vetted.returncode, vetted.stdout + vetted.stderr)
            with open(join(crate, "model/loader.go"), "a") as loader_file:
                loader_file.write("//\n")
            self.assertEqual("embedded", embed_consumer(self.consumer, self.source, "demo_replay_double"))
            with open(join(crate, "go.mod"), "w") as mod_file:
                mod_file.write(mod.replace("wazero v1.12.0", "wazero v1.0.0"))
            with self.assertRaises(GateError) as raised:
                embed_consumer(self.consumer, self.source, "demo_replay_double")
            self.assertIn("wazero", raised.exception.cause)

    def test_a_served_project_makes_mlserver_stale_until_its_loader_is_current(self):
        from mlmodels._embed import embed_loader, stale_consumers

        mlserver = join(self.source, "may", "mlserver")
        os.makedirs(mlserver)
        self.record()
        self.release()
        self.assertEqual([self.consumer, mlserver], stale_consumers(self.source))
        embed_loader(mlserver, "python")
        self.assertEqual([self.consumer], stale_consumers(self.source))
        with open(join(mlserver, "src/main/python/serving/model/loader.py"), "a") as loader_file:
            loader_file.write("#")
        self.assertEqual([self.consumer, mlserver], stale_consumers(self.source))
        embed_loader(mlserver, "python")
        self.assertEqual([self.consumer], stale_consumers(self.source))
        with open(join(mlserver, "src/main/python/serving/model/vocabulary.py"), "a") as vocabulary_file:
            vocabulary_file.write("PROJECT_ALIAS_RELEASE = 'other'\n")
        self.assertEqual([self.consumer, mlserver], stale_consumers(self.source))
        embed_loader(mlserver, "python")
        os.makedirs(join(mlserver, "src/main/python/serving/model/__pycache__"))
        with open(join(mlserver, "src/main/python/serving/model/project.py"), "w") as old_file:
            old_file.write("# a file from an earlier version\n")
        self.assertEqual([self.consumer, mlserver], stale_consumers(self.source))
        self.assertEqual(["project.py"], embed_loader(mlserver, "python"))
        self.assertEqual(["__init__.py", "__pycache__", "loader.py", "vocabulary.py"], sorted(os.listdir(join(mlserver, "src/main/python/serving/model"))))
        self.assertEqual([self.consumer], stale_consumers(self.source))

    def test_inputs_change_with_the_pins(self):
        from mlmodels._metadata import inputs_changed

        self.assertTrue(inputs_changed(self.workspace, self.pins))
        self.record()
        self.assertFalse(inputs_changed(self.workspace, self.pins))
        with open(self.pins, "w") as pins_file:
            pins_file.write("numpy==2.1\n")
        self.assertTrue(inputs_changed(self.workspace, self.pins))

    def test_an_embedded_only_project_is_not_registered(self):
        from mlmodels._registry import register_preview

        self.assertIsNone(register_preview(build_project("wasm"), "demo_replay_double", "http://127.0.0.1:9", {"kind": "embedded", "language": "rust"}))

    def test_the_signature_may_grow_but_not_change_what_was_released(self):
        from mlmodels._errors import GateError
        from mlmodels._metadata import read_metadata, signature_findings

        self.record()
        self.release()
        released = read_metadata(self.workspace)["release"]["signature"]
        grown = json.loads(json.dumps(released))
        grown["outputs"].append({**grown["outputs"][0], "name": "demo_extra"})
        grown["inputs"].append({**grown["inputs"][0], "name": "demo_optional", "parameters": {**grown["inputs"][0]["parameters"], "required": False}})
        self.assertEqual([], signature_findings(released, grown))
        for change in (
            lambda signature: signature["outputs"].pop(0),
            lambda signature: signature["inputs"][0].update({"datatype": "INT64"}),
            lambda signature: signature["inputs"].append({**signature["inputs"][0], "name": "demo_new"}),
        ):
            broken = json.loads(json.dumps(released))
            change(broken)
            self.assertTrue(signature_findings(released, broken))
        with self.assertRaises(GateError) as raised:
            self.record(project_dir=self.project_with_signature(lambda signature: signature["outputs"].pop(0)))
        self.assertEqual(("Package", "signature"), (raised.exception.stage, raised.exception.gate))

    def additive(self, signature):
        signature["inputs"].append({**signature["inputs"][0], "name": "demo_optional", "parameters": {**signature["inputs"][0]["parameters"], "required": False}})

    def test_a_content_change_then_a_breaking_edit_at_the_same_signature_version_is_refused(self):
        from mlmodels._errors import GateError
        from mlmodels._metadata import read_metadata

        self.record()
        self.release()
        self.record(project_dir=build_project("wasm", golden_out=3.5))
        self.assertIsNone(read_metadata(self.workspace)["release"])
        with self.assertRaises(GateError) as raised:
            self.record(project_dir=self.project_with_signature(lambda signature: signature["outputs"].pop(0)))
        self.assertEqual(("Package", "signature"), (raised.exception.stage, raised.exception.gate))

    def test_a_higher_signature_version_may_break_and_a_lower_one_is_refused(self):
        from mlmodels._errors import GateError
        from mlmodels._metadata import read_metadata

        def project(number, change=lambda signature: None):
            return self.project_with_signature(lambda signature: (signature.update(signature_version=number), change(signature)))

        self.record(project_dir=project(1001))
        self.release()
        with self.assertRaises(GateError):
            self.record(project_dir=project(1000))
        self.record(project_dir=project(1002, lambda signature: signature["outputs"].pop(0)))
        self.assertEqual(1001, read_metadata(self.workspace)["baseline"]["signature_version"])

    def test_a_released_workspace_with_no_baseline_is_seeded_from_its_release(self):
        from mlmodels._errors import GateError
        from mlmodels._metadata import read_metadata, write_metadata

        self.record()
        self.release()
        metadata = read_metadata(self.workspace)
        del metadata["baseline"]
        write_metadata(self.workspace, metadata)
        with self.assertRaises(GateError):
            self.record(project_dir=self.project_with_signature(lambda signature: signature["outputs"].pop(0)))
        self.record(project_dir=self.project_with_signature(self.additive))
        self.assertEqual(metadata["release"]["signature"], read_metadata(self.workspace)["baseline"])

    def test_a_release_writes_the_baseline_of_a_served_target_only(self):
        from mlmodels._metadata import read_metadata

        self.record()
        self.release()
        metadata = read_metadata(self.workspace)
        self.assertEqual(metadata["release"]["signature"], metadata["baseline"])
        shutil.rmtree(self.workspace)
        os.makedirs(self.workspace)
        with open(join(self.workspace, "notebook.ipynb"), "w") as notebook_file:
            json.dump({"cells": [{"cell_type": "code", "source": ["x = 1\n"]}]}, notebook_file)
        self.record(target={"kind": "embedded", "language": "rust"})
        self.release()
        self.assertNotIn("baseline", read_metadata(self.workspace))

    def test_live_signature_versions_are_ranked_newest_first_with_the_unsuffixed_model_last(self):
        from mlmodels._release import live_signatures

        self.assertEqual([(1001, "a_1001"), (1000, "a_1000"), (0, "a")], live_signatures("a", ["a", "a_1000", "a_1001", "a_b_1000", "ab", "a_1000_preview", "b_1002"]))

    def live_models(self, client, *names, preview=()):
        for name in (*names, *preview):
            client.create_registered_model(name)
            version = client.create_model_version(name, "file:///nowhere", tags={"content_sha256": name, "project_flavour": "wasm"})
            client.set_registered_model_alias(name, "preview" if name in preview else "release", version.version)

    def serve(self, *names):
        import http.server
        import threading

        index = json.dumps([{"name": name, "version": "10.200.1", "state": "READY"} for name in names]).encode()

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(handler):
                handler.send_response(200)
                handler.send_header("Content-Type", "application/json")
                handler.end_headers()
                handler.wfile.write(index)

            def log_message(handler, *arguments):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def publish_at(self, signature_version, models, preview=(), url=None):
        from mlflow import MlflowClient
        from mlmodels._release import publish_workspace

        uri = f"sqlite:///{join(tempfile.mkdtemp(), 'mlflow.db')}"
        client = MlflowClient(uri, uri)
        self.live_models(client, *models, preview=preview)
        self.record(project_dir=build_project("wasm", signature_version=signature_version))
        self.release()
        publish_workspace("demo_replay_double", self.workspace, uri, url or self.serve(f"demo_replay_double_{signature_version}"), self.source)
        return {model.name for model in client.search_registered_models() if "release" in model.aliases}

    def test_publishing_a_new_signature_version_retires_all_but_the_two_newest(self):
        self.assertEqual(
            {"demo_replay_double_1000", "demo_replay_double_1001", "demo_replay_doubled_1000"}, self.publish_at(1001, ["demo_replay_double", "demo_replay_double_1000", "demo_replay_doubled_1000"])
        )

    def test_two_live_signature_versions_retire_nothing(self):
        self.assertEqual({"demo_replay_double_1000", "demo_replay_double_1001"}, self.publish_at(1001, ["demo_replay_double_1000"]))

    def test_a_preview_only_signature_version_counts_for_nothing(self):
        self.assertEqual({"demo_replay_double_1000", "demo_replay_double_1001"}, self.publish_at(1001, ["demo_replay_double_1000"], preview=["demo_replay_double_1002"]))

    def test_publishing_an_older_signature_version_keeps_it_though_two_newer_are_live(self):
        self.assertEqual({"demo_replay_double_1000", "demo_replay_double_1001", "demo_replay_double_1002"}, self.publish_at(1000, ["demo_replay_double_1001", "demo_replay_double_1002"]))

    def test_a_signature_version_a_client_still_pins_is_not_retired(self):
        client_dir = join(self.source, "meg", "client")
        os.makedirs(client_dir)
        with open(join(client_dir, "config.yaml"), "w") as config_file:
            config_file.write("resource: https://mlserver/v2/models/demo_replay_double/infer\n")
        self.assertEqual({"demo_replay_double", "demo_replay_double_1000", "demo_replay_double_1001"}, self.publish_at(1001, ["demo_replay_double", "demo_replay_double_1000"]))

    def test_nothing_is_retired_when_the_published_version_is_not_confirmed_served(self):
        from unittest import mock

        with mock.patch("mlmodels._release.wait_served", return_value="unreachable"):
            live = self.publish_at(1001, ["demo_replay_double", "demo_replay_double_1000"])
        self.assertEqual({"demo_replay_double", "demo_replay_double_1000", "demo_replay_double_1001"}, live)

    def test_status_counts_what_a_registry_shows_beyond_the_two_live_versions_and_git(self):
        from mlflow import MlflowClient
        from mlmodels._embed import embed_consumer
        from mlmodels._release import publish_workspace, status_lines

        self.record()
        self.release()
        uri = f"sqlite:///{join(tempfile.mkdtemp(), 'mlflow.db')}"
        publish_workspace("demo_replay_double", self.workspace, uri)
        embed_consumer(self.consumer, self.source, "demo_replay_double")
        client = MlflowClient(uri, uri)
        self.assertEqual([], status_lines(self.source, uri))
        self.live_models(client, "demo_replay_double_1001")
        self.assertEqual(1, len(status_lines(self.source, uri)))
        self.live_models(client, "demo_replay_double_1002")
        self.assertEqual(2, len(status_lines(self.source, uri)))
        client.delete_registered_model_alias("demo_replay_double_1002", "release")
        self.assertEqual(1, len(status_lines(self.source, uri)))
        client_dir = join(self.source, "meg", "client")
        os.makedirs(client_dir)

        def pin(model):
            with open(join(client_dir, "config.yaml"), "w") as config_file:
                config_file.write(f"resource: https://mlserver/v2/models/{model}/infer\n")

        pin("demo_replay_double_1000")
        self.assertEqual(2, len(status_lines(self.source, uri)))
        pin("demo_replay_double_1001")
        self.assertEqual(1, len(status_lines(self.source, uri)))
        client.delete_registered_model_alias("demo_replay_double_1001", "release")
        self.assertEqual(1, len(status_lines(self.source, uri)))

    def test_an_embedded_project_may_change_its_released_signature_in_place_and_a_served_one_may_not(self):
        from mlmodels._errors import GateError
        from mlmodels._metadata import read_metadata

        embedded = {"kind": "embedded", "language": "rust"}
        self.record(target=embedded)
        self.release()
        released = read_metadata(self.workspace)["release"]["signature"]
        changed = self.project_with_signature(lambda signature: signature["outputs"].pop(0))
        recorded = self.record(project_dir=changed, target=embedded)
        assert recorded is not None
        self.assertEqual(released, read_metadata(self.workspace)["release"]["signature"])
        with self.assertRaises(GateError) as raised:
            self.record(project_dir=self.project_with_signature(lambda signature: signature["outputs"].pop(0)))
        self.assertEqual(("Package", "signature"), (raised.exception.stage, raised.exception.gate))

    def project_with_signature(self, change):
        project_dir = build_project("wasm")
        with open(join(project_dir, "signature.json")) as signature_file:
            signature = json.load(signature_file)
        change(signature)
        with open(join(project_dir, "signature.json"), "w") as signature_file:
            json.dump(signature, signature_file)
        return project_dir

    def test_publishing_registers_by_content_sets_the_tags_moves_release_and_clears_preview(self):
        from mlflow import MlflowClient
        from mlmodels._release import publish_workspace, wait_served

        self.record()
        self.release()
        uri = f"sqlite:///{join(tempfile.mkdtemp(), 'mlflow.db')}"
        from mlmodels._registry import register_project

        previewed = register_project(join(self.workspace, "project"), "demo_replay_double_1000", uri)
        self.assertEqual("published", publish_workspace("demo_replay_double", self.workspace, uri))
        client = MlflowClient(uri, uri)
        model = client.get_registered_model("demo_replay_double_1000")
        self.assertEqual({"release": str(previewed)}, {alias: str(version) for alias, version in model.aliases.items()})
        tags = client.get_model_version("demo_replay_double_1000", previewed).tags
        self.assertEqual("10.200.1", tags["release_version"])
        self.assertEqual(json.loads(tags["metadata"])["release"]["timestamp"], tags["released_at"])
        self.assertEqual("published", publish_workspace("demo_replay_double", self.workspace, uri))
        register_project(join(self.workspace, "project"), "demo_replay_double_1000", uri)
        client.delete_registered_model_alias("demo_replay_double_1000", "preview")
        self.assertNotIn("preview", client.get_registered_model("demo_replay_double_1000").aliases)
        self.assertEqual("unreachable", wait_served("http://127.0.0.1:9", "demo_replay_double", "10.200.1", timeout=1))

    def test_status_names_a_stale_consumer_and_nothing_else_when_everything_matches(self):
        from mlmodels._embed import embed_consumer
        from mlmodels._release import status_lines

        self.record()
        self.release()
        self.assertEqual(["WARN"], [level for level, _ in status_lines(self.source)])
        embed_consumer(self.consumer, self.source, "demo_replay_double")
        self.assertEqual([], status_lines(self.source))


class DocumentTest(unittest.TestCase):
    def test_a_document_keeps_its_order_and_puts_scalar_lists_and_flat_objects_on_one_line(self):
        from mlmodels._document import write_json

        document = {
            "schema": 2,
            "tensor": {"name": "x", "datatype": "FP64", "shape": [1], "data": [1.5]},
            "nested": {"inner": {"a": 1}, "list": [{"b": 2}]},
            "empty": {},
            "none": None,
        }
        path = join(tempfile.mkdtemp(), "document.json")
        write_json(path, document)
        with open(path) as document_file:
            text = document_file.read()
        self.assertEqual(document, json.loads(text))
        self.assertEqual(list(document), list(json.loads(text)))
        self.assertIn('  "tensor": {"name": "x", "datatype": "FP64", "shape": [1], "data": [1.5]},\n', text)
        self.assertIn('    "inner": {"a": 1},\n', text)
        self.assertIn('    "list": [\n      {"b": 2}\n    ]\n', text)
        self.assertTrue(text.endswith("}\n"))
        wide = {"names": [f"name_{index:03d}" for index in range(40)]}
        write_json(path, wide)
        with open(path) as document_file:
            self.assertGreater(len(document_file.read().splitlines()), 40)


class RegistryToolsTest(unittest.TestCase):
    def test_the_registry_address_must_be_the_proxy_name_and_not_a_published_port(self):
        from mlmodels._registry import registry_address

        self.assertEqual("https://mlflow.proxy.example.com", registry_address("https://mlflow.proxy.example.com"))
        for uri in ("http://macmini-may.local:32413", "", None):
            with self.assertRaises(ValueError):
                registry_address(uri)

    def test_a_finding_maps_to_one_hint_and_a_repeat_is_not_repeated(self):
        from mlmodels._lint_project import fix_hints

        self.assertEqual(1, len(fix_hints(["PJ003", "PJ013", "PJ015"])))
        self.assertEqual(2, len(fix_hints(["PJ003", "CP004"])))
        self.assertEqual([], fix_hints(["ZZ999"]))


class NotebookLintTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.notebook_dir = join(self.root, "demo", "calc", "run")
        os.makedirs(self.notebook_dir)
        self.path = join(self.notebook_dir, "notebook.ipynb")

    def notebook(self, **changes):
        import json

        from mlmodels._lint_notebook import stage_heading

        title = "# demo / calc / run\n\n**Intent**\n- Output a calculation\n\n**Data**\n- `golden`: the samples"
        cells = [
            {"cell_type": "markdown", "metadata": {}, "source": title},
            {"cell_type": "markdown", "metadata": {}, "source": stage_heading("Setup")},
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": 'from mlmodels import setup_workspace\n\nws = setup_workspace("demo/calc/run", {"kind": "served"})\n',
            },
            {"cell_type": "markdown", "metadata": {}, "source": stage_heading("Package")},
        ]
        notebook = {"cells": cells, "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
        notebook.update(changes)
        with open(self.path, "w") as notebook_file:
            json.dump(notebook, notebook_file)
        return notebook

    def rules(self):
        from mlmodels._lint_notebook import lint_notebook

        return sorted({rule for rule, _, _ in lint_notebook(self.path)})

    def test_valid_notebook_has_no_findings(self):
        self.notebook()
        self.assertEqual([], self.rules())

    def test_outputs_are_found_and_stripped(self):
        from mlmodels._lint_notebook import fix_notebook

        notebook = self.notebook()
        notebook["cells"][2]["outputs"] = [{"output_type": "stream"}]
        notebook["cells"][2]["execution_count"] = 3
        self.notebook(cells=notebook["cells"])
        self.assertEqual(["NB002"], self.rules())
        self.assertTrue(fix_notebook(self.path))
        self.assertEqual([], self.rules())
        self.assertFalse(fix_notebook(self.path))

    def test_wrong_title_is_found(self):
        notebook = self.notebook()
        notebook["cells"][0]["source"] = notebook["cells"][0]["source"].replace("# demo / calc / run", "# demo / calc / other")
        self.notebook(cells=notebook["cells"])
        self.assertEqual(["NB003"], self.rules())

    def test_a_title_cell_must_hold_only_the_labelled_short_dot_points(self):
        base = "# demo / calc / run\n\n"
        intent = "**Intent**\n- Outputs a calculation."
        data = "**Data**\n- `golden` is the samples."
        self.notebook()
        self.assertEqual([], self.rules())
        for source in (
            base + data,
            base + intent,
            base + intent + "\n\n**Data**\n\n**Status**\n- A placeholder.",
            base + intent + "\n\n" + data + "\n\n**Purpose**\n- To calculate.",
            base + intent + "\n\n" + data + "\n\n**Notes:**\n- one",
            base + intent + "\nA sentence in place of a dot point.\n\n" + data,
            base + intent + "\n\n" + data + "\n\n| Term | In This Notebook |\n|---|---|",
            base + intent + "\n\n" + data + "\n\n**Status**\n- " + "word " * 26,
        ):
            notebook = self.notebook()
            notebook["cells"][0]["source"] = source
            self.notebook(cells=notebook["cells"])
            self.assertEqual(["NB004"], self.rules(), source)

    def test_a_dot_point_may_have_indented_sub_bullets_which_are_also_kept_short(self):
        base = "# demo / calc / run\n\n**Intent**\n- Outputs a calculation.\n\n**Data**\n- `golden` is the samples.\n\n**Future**\n- Overall: the design holds:\n  - Keep it small.\n- Phase 1: the build:\n  - Build it.\n  - Ship it.\n"
        notebook = self.notebook()
        notebook["cells"][0]["source"] = base
        self.notebook(cells=notebook["cells"])
        self.assertEqual([], self.rules())
        notebook["cells"][0]["source"] = base + "  - " + "word " * 26
        self.notebook(cells=notebook["cells"])
        self.assertEqual(["NB004"], self.rules())

    def test_a_future_dot_point_must_be_overall_or_a_phase(self):
        notebook = self.notebook()
        notebook["cells"][0]["source"] = "# demo / calc / run\n\n**Intent**\n- Outputs a calculation.\n\n**Data**\n- `golden` is the samples.\n\n**Future**\n- Build it.\n"
        self.notebook(cells=notebook["cells"])
        self.assertEqual(["NB004"], self.rules())

    def test_an_intent_must_name_every_output_of_the_signature_and_nothing_it_lacks(self):
        from mlmodels._signature import build_signature, signature_input, signature_output

        signature = build_signature(
            "demo_calc_run",
            [signature_input("calc_in", "none", "An input.")],
            [signature_output("calc_out_low", "none", "Low.", datatype="FP64"), signature_output("calc_out_high", "none", "High.", datatype="FP64")],
        )
        with open(join(self.notebook_dir, "signature.json"), "w") as signature_file:
            json.dump(signature, signature_file)
        base = "# demo / calc / run\n\n**Intent**\n- {}\n\n**Data**\n- `golden`"
        for intent, expected in (
            ("Output `calc_out_low` and `calc_out_high`.", []),
            ("Output `calc_out_{low,high}`.", []),
            ("Output `calc_out_*`.", []),
            ("Output `calc_out_low`.", ["NB013"]),
            ("Output `calc_out_{low,high}` and `calc_old`.", ["NB013"]),
            ("Output `calc_nothing_*` and `calc_out_{low,high}`.", ["NB013"]),
        ):
            notebook = self.notebook()
            notebook["cells"][0]["source"] = base.format(intent)
            self.notebook(cells=notebook["cells"])
            self.assertEqual(expected, self.rules(), intent)

    def test_a_stage_heading_with_extra_text_is_found(self):
        notebook = self.notebook()
        notebook["cells"][3]["source"] = "## Package\n\n- **Intent:** Do it."
        self.notebook(cells=notebook["cells"])
        self.assertEqual(["NB006"], self.rules())

    def test_stages_out_of_order_are_found(self):
        notebook = self.notebook()
        notebook["cells"][1], notebook["cells"][3] = notebook["cells"][3], notebook["cells"][1]
        self.notebook(cells=notebook["cells"])
        self.assertIn("NB005", self.rules())

    def test_magic_path_and_secret_are_found(self):
        notebook = self.notebook()
        notebook["cells"][2]["source"] += '%matplotlib inline\npath = "/Users/someone/file"\ntoken = "abc"\n'
        self.notebook(cells=notebook["cells"])
        self.assertEqual(["NB007"], self.rules())

    def test_wrong_model_name_is_found(self):
        notebook = self.notebook()
        notebook["cells"][2]["source"] = 'from mlmodels import setup_workspace\n\nws = setup_workspace("demo/calc", {"kind": "served"})\n'
        self.notebook(cells=notebook["cells"])
        self.assertEqual(["NB008"], self.rules())

    def test_a_workspace_with_git_ignored_data_says_so_in_its_data_line(self):
        subprocess.run(["git", "init", "-q", self.root], check=True, capture_output=True)
        with open(join(self.root, ".gitignore"), "w") as ignore_file:
            ignore_file.write("demo/calc/run/data/*/*/\ndemo/calc/run/project/\n")
        base = "# demo / calc / run\n\n**Intent**\n- Output a calculation\n\n**Data**\n- {}"
        for data, expected in (
            ("`golden`", ["NB014"]),
            ("Personal data: `data/` git-ignored", ["NB014"]),
            ("Personal data: `data/` and `project/` git-ignored", []),
        ):
            notebook = self.notebook()
            notebook["cells"][0]["source"] = base.format(data)
            self.notebook(cells=notebook["cells"])
            self.assertEqual(expected, self.rules(), data)

    def test_star_import_and_sys_path_are_found(self):
        notebook = self.notebook()
        notebook["cells"][2]["source"] += "from mlmodels.data import *\nimport sys\nsys.path.append('x')\n"
        self.notebook(cells=notebook["cells"])
        self.assertEqual(["NB011", "NB012"], self.rules())

    def test_a_rename_is_found_and_an_added_column_is_not(self):
        notebook = self.notebook()
        notebook["cells"][2]["source"] += "frame = frame.with_columns(x=1)\n"
        self.notebook(cells=notebook["cells"])
        self.assertEqual([], self.rules())
        notebook["cells"][2]["source"] += "frame = frame.rename({'a': 'b'})\n"
        self.notebook(cells=notebook["cells"])
        self.assertEqual(["NB017"], self.rules())

    def test_a_name_bound_in_one_stage_is_not_read_by_a_later_one(self):
        notebook = self.notebook()
        notebook["cells"][2]["source"] += "gain = 2.0\n\n\ndef scale(value):\n    return value * 3\n"
        self.notebook(cells=notebook["cells"])
        self.assertEqual([], self.rules())
        notebook["cells"].append({"cell_type": "code", "id": "later", "metadata": {}, "outputs": [], "execution_count": None, "source": "print(gain, scale(1))\n"})
        self.notebook(cells=notebook["cells"])
        self.assertEqual(["NB018"], self.rules())
        notebook["cells"][-1]["source"] = "gain = ws.params['gain']\nprint(gain, scale(1))\n"
        self.notebook(cells=notebook["cells"])
        self.assertEqual([], self.rules())

    def test_a_plotting_cell_must_collapse_its_output(self):
        notebook = self.notebook()
        notebook["cells"][2]["source"] += "prepare_plot(ws)\n"
        self.notebook(cells=notebook["cells"])
        self.assertEqual(["NB016"], self.rules())
        notebook["cells"][2]["metadata"] = {"jupyter": {"outputs_hidden": True}}
        self.notebook(cells=notebook["cells"])
        self.assertEqual([], self.rules())

    def test_command_line_accepts_new_and_lint_and_the_old_lint_form(self):
        from mlmodels._command import notebook_command as main

        root = tempfile.mkdtemp()
        self.assertEqual(0, main(["new", "egcli", "calc", "run", "static", "--root", root]))
        path = join(root, "egcli", "calc", "run", "notebook.ipynb")
        self.assertEqual(0, main(["lint", path]))
        self.assertEqual(0, main([path]))
        self.assertEqual(1, main(["new", "egcli", "calc", "run", "static", "--root", root]))

    def test_scaffold_passes_every_check_and_refuses_to_overwrite(self):
        from mlmodels._lint_notebook import lint_notebook
        from mlmodels._lint_workspace import lint_workspace
        from mlmodels._scaffold import scaffold_notebook

        root = tempfile.mkdtemp()
        for flavour in ("static", "wasm"):
            created = scaffold_notebook(root, "example", "calc", flavour, flavour)
            self.assertEqual([], lint_notebook(join(root, "example", "calc", flavour, "notebook.ipynb")))
            self.assertEqual([], lint_workspace(join(root, "example", "calc", flavour)))
            self.assertTrue(all(os.path.exists(path) for path in created))
        scaffold_notebook(root, "example", "calc", "kept", "static", local=True)
        self.assertEqual([], lint_notebook(join(root, "example", "calc", "kept", "notebook.ipynb")))
        with open(join(root, "example", "calc", "kept", "notebook.ipynb")) as kept_file:
            kept = json.load(kept_file)
        self.assertIn('{"kind": "local"}', "".join("".join(cell["source"]) for cell in kept["cells"]))
        self.assertNotIn("Register", [cell["source"][0] for cell in kept["cells"] if cell["cell_type"] == "markdown"])
        with self.assertRaises(ValueError):
            scaffold_notebook(root, "example", "calc", "static", "static")
        with self.assertRaises(ValueError):
            scaffold_notebook(root, "example", "calc", "other", "guess")
        with self.assertRaises(ValueError):
            scaffold_notebook(root, "Bad-Name", "calc", "run", "static")


class WorkspaceLintTest(unittest.TestCase):
    NAME = "calc_run_voltage"

    def setUp(self):
        self.notebook_dir = join(tempfile.mkdtemp(), "demo", "calc", "run")
        self.source_dir = tempfile.mkdtemp()
        os.makedirs(join(self.source_dir, "max", "demo"))
        os.makedirs(join(self.notebook_dir, "data"))
        open(join(self.notebook_dir, "notebook.ipynb"), "w").close()
        open(join(self.notebook_dir, "data/.gitkeep"), "w").close()
        self.write_run(1000, self.NAME)

    def write_run(self, run, name):
        import hashlib

        directory = join(self.notebook_dir, "data", str(run))
        os.makedirs(directory, exist_ok=True)
        with open(join(directory, f"{name}.csv"), "w") as data_file:
            data_file.write("a\n1\n")
        with open(join(directory, f"{name}.csv"), "rb") as data_file:
            digest = hashlib.sha256(data_file.read()).hexdigest()
        with open(join(directory, f"{name}.json"), "w") as sidecar_file:
            json.dump({"schema": 2, "run": run, "label": "demo", "live": False, "name": name, "sha256": digest}, sidecar_file)

    def rules(self):
        from mlmodels._lint_workspace import lint_workspace

        return sorted({rule for rule, _ in lint_workspace(self.notebook_dir, self.source_dir)})

    def test_valid_workspace_has_no_findings(self):
        self.assertEqual([], self.rules())

    def test_a_notebook_name_may_not_be_mistaken_for_a_signature_version(self):
        from mlmodels._lint_workspace import lint_workspace

        for notebook, flagged in (("run", False), ("co2", False), ("1000", True), ("run_1000", True), ("run_25", True)):
            with self.subTest(notebook=notebook):
                renamed = join(dirname(self.notebook_dir), notebook)
                if renamed != self.notebook_dir:
                    shutil.rmtree(renamed, ignore_errors=True)
                    shutil.copytree(self.notebook_dir, renamed)
                self.assertEqual(flagged, "WS015" in {rule for rule, _ in lint_workspace(renamed, self.source_dir)})

    def test_the_single_command_reaches_the_workspace_lint(self):
        from mlmodels.__main__ import main

        self.assertEqual(0, main(["workspace", self.notebook_dir]))
        open(join(self.notebook_dir, "notes.txt"), "w").close()
        self.assertEqual(1, main(["workspace", self.notebook_dir]))

    def test_a_notebook_name_is_unique_per_module_and_loader_language(self):
        module_dir = dirname(dirname(self.notebook_dir))

        def write_target(model, target):
            directory = join(module_dir, model, "run")
            os.makedirs(directory, exist_ok=True)
            with open(join(directory, "metadata.json"), "w") as metadata_file:
                json.dump({"target": target}, metadata_file)

        write_target("calc", {"kind": "embedded", "language": "rust"})
        write_target("other", {"kind": "embedded", "language": "python"})
        self.assertEqual([], self.rules())
        write_target("other", {"kind": "embedded", "language": "rust"})
        self.assertEqual(["WS013"], self.rules())
        write_target("other", {"kind": "local"})
        self.assertEqual([], self.rules())
        write_target("calc", {"kind": "served"})
        write_target("other", {"kind": "served"})
        self.assertEqual(["WS013"], self.rules())

    def test_an_embedded_workspace_needs_a_module_of_its_name_except_the_examples(self):
        def write_target(kind):
            with open(join(self.notebook_dir, "metadata.json"), "w") as metadata_file:
                json.dump({"target": {"kind": kind, "language": "rust"}}, metadata_file)

        write_target("embedded")
        self.assertEqual([], self.rules())
        os.rmdir(join(self.source_dir, "max", "demo"))
        self.assertEqual(["WS014"], self.rules())
        write_target("local")
        self.assertEqual([], self.rules())
        write_target("embedded")
        example_dir = join(dirname(dirname(dirname(self.notebook_dir))), "example", "calc", "run")
        os.makedirs(example_dir)
        shutil.copy(join(self.notebook_dir, "metadata.json"), example_dir)
        from mlmodels._lint_workspace import lint_workspace

        self.assertNotIn("WS014", [rule for rule, _ in lint_workspace(example_dir, self.source_dir)])

    def test_a_plan_file_is_a_finding_since_the_notebook_header_holds_the_plan(self):
        open(join(self.notebook_dir, "plan.md"), "w").close()
        self.assertEqual(["WS003"], self.rules())

    def test_stray_file_and_second_notebook_are_found(self):
        open(join(self.notebook_dir, "notes.txt"), "w").close()
        open(join(self.notebook_dir, "other.ipynb"), "w").close()
        self.assertEqual(["WS002", "WS003"], self.rules())

    def test_a_model_directory_needs_its_document_and_the_file_the_document_hashes(self):
        import hashlib

        directory = join(self.notebook_dir, "model/1000")
        os.makedirs(directory)
        self.assertEqual(["WS011"], self.rules())
        with open(join(directory, "model.py"), "w") as model_file:
            model_file.write("x = 1\n")
        digest = hashlib.sha256(b"x = 1\n").hexdigest()
        document = {"schema": 1, "model": 1000, "label": "demo", "flavour": "pyfunc", "runs": [], "sha256": digest}
        with open(join(directory, "model.json"), "w") as document_file:
            json.dump(document, document_file)
        self.assertEqual([], self.rules())
        with open(join(directory, "model.py"), "a") as model_file:
            model_file.write("y = 2\n")
        self.assertEqual(["WS011"], self.rules())

    def test_a_directory_that_is_not_a_run_number_is_found(self):
        os.makedirs(join(self.notebook_dir, "data/training"))
        self.assertEqual(["WS005"], self.rules())

    def test_runs_are_numbered_from_1000_and_may_have_gaps(self):
        self.write_run(999, self.NAME)
        self.assertEqual(["WS005"], self.rules())
        shutil.rmtree(join(self.notebook_dir, "data/999"))
        self.write_run(1003, self.NAME)
        self.assertEqual([], self.rules())

    def test_a_run_needs_a_label_and_a_live_flag(self):
        sidecar = join(self.notebook_dir, "data/1000", f"{self.NAME}.json")
        with open(sidecar) as sidecar_file:
            meta = json.load(sidecar_file)
        del meta["label"], meta["live"]
        with open(sidecar, "w") as sidecar_file:
            json.dump(meta, sidecar_file)
        self.assertEqual(["WS008"], self.rules())

    def test_a_required_input_must_be_a_column_of_every_dataset_of_a_workspace_with_a_fitted_model(self):
        directory = join(self.notebook_dir, "model/1000")
        os.makedirs(directory)
        with open(join(directory, "model.json"), "w") as document_file:
            json.dump({"schema": 1, "model": 1000, "label": "demo", "flavour": "static", "runs": [], "sha256": "x", "constants": {}}, document_file)
        with open(join(self.notebook_dir, "signature.json"), "w") as signature_file:
            json.dump({"inputs": [{"name": "b", "parameters": {"required": True}}, {"name": "c", "parameters": {"required": False}}], "outputs": []}, signature_file)
        self.assertEqual([], self.rules())
        with open(join(directory, "model.json"), "w") as document_file:
            json.dump({"schema": 1, "model": 1000, "label": "demo", "flavour": "pyfunc", "runs": [], "sha256": "x"}, document_file)
        with open(join(directory, "model.py"), "w") as model_file:
            model_file.write("x")
        self.assertEqual(["WS011", "WS012"], self.rules())

    def test_dataset_must_be_a_csv_named_for_the_model_and_notebook(self):
        open(join(self.notebook_dir, "data/1000/other_voltage.csv"), "w").close()
        open(join(self.notebook_dir, "data/1000/calc_run_voltage.txt"), "w").close()
        self.assertEqual(["WS006"], self.rules())

    def test_every_run_of_a_dataset_must_share_its_columns(self):
        self.write_run(1001, self.NAME)
        self.assertEqual([], self.rules())
        with open(join(self.notebook_dir, "data/1001", f"{self.NAME}.csv"), "w") as data_file:
            data_file.write("a,b\n1,2\n")
        self.assertIn("WS009", self.rules())

    def test_an_inferred_column_must_exist_in_the_csv(self):
        sidecar = join(self.notebook_dir, "data/1000", f"{self.NAME}.json")
        with open(sidecar) as sidecar_file:
            meta = json.load(sidecar_file)
        meta["inferred"] = ["a"]
        with open(sidecar, "w") as sidecar_file:
            json.dump(meta, sidecar_file)
        self.assertEqual([], self.rules())
        meta["inferred"] = ["missing"]
        with open(sidecar, "w") as sidecar_file:
            json.dump(meta, sidecar_file)
        self.assertEqual(["WS010"], self.rules())

    def test_a_csv_needs_a_sidecar_that_describes_it(self):
        os.remove(join(self.notebook_dir, "data/1000", f"{self.NAME}.json"))
        self.assertEqual(["WS008"], self.rules())
        self.write_run(1000, self.NAME)
        with open(join(self.notebook_dir, "data/1000", f"{self.NAME}.csv"), "a") as data_file:
            data_file.write("2\n")
        self.assertEqual(["WS008"], self.rules())

    def test_bad_notebook_name_is_found(self):
        bad = join(os.path.dirname(self.notebook_dir), "Run-Two")
        os.rename(self.notebook_dir, bad)
        self.notebook_dir = bad
        self.assertIn("WS001", self.rules())


class SpecSyncTest(unittest.TestCase):
    SPEC = join(ROOT, "rue/mlmodels/src/build/resources/doc/model.md")

    def setUp(self):
        with open(self.SPEC) as spec:
            self.spec = spec.read()

    def section(self, heading):
        start = self.spec.index(heading)
        end = self.spec.find("\n#", start + len(heading))
        return self.spec[start : end if end != -1 else len(self.spec)]

    def test_check_identifiers_agree_both_ways(self):

        in_spec = set(re.findall(r"^\| ((?:PJ|NB|WS|PM|AC|CP|RP|MD)\d{3}) \|", self.spec, re.MULTILINE))
        in_code = set()
        for module in sorted(glob.glob(join(ROOT, "rue/mlmodels/src/main/python/mlmodels/*.py")) + glob.glob(join(ROOT, "rue/mlmodels/src/main/python/mlmodels/runtime/*.py"))):
            with open(module) as source:
                in_code |= set(re.findall(r'"((?:PJ|NB|WS|PM|AC|CP|RP|MD)\d{3})"', source.read()))
        self.assertTrue(in_spec and in_code)
        self.assertEqual(in_spec, in_code)

    def test_every_requirement_is_covered_by_a_check_or_by_review(self):

        enforced = {}
        for identifier, requirements in re.findall(r"^\| ((?:PJ|NB|WS|PM|AC|CP|RP|MD)\d{3}) \|.*\| (R[0-9, R]+) \|$", self.spec, re.MULTILINE):
            for requirement in re.findall(r"R\d+", requirements):
                enforced.setdefault(requirement, set()).add(identifier)
        coverage = {}
        for requirement, checked_by in re.findall(r"^\| (R\d+) \| ([^|]+) \|$", self.section("### 9.2 Coverage of the requirements"), re.MULTILINE):
            coverage[requirement] = set() if checked_by.strip() == "Review" else {item.strip() for item in checked_by.split(",")}
        defined = set(re.findall(r"^\| (R\d+) \| (?:Standard|Parity|Delivery|Change) \|", self.spec, re.MULTILINE))
        self.assertTrue(enforced and coverage and defined)
        self.assertEqual(defined, set(coverage))
        self.assertEqual({requirement: ids for requirement, ids in coverage.items() if ids}, enforced)

    def test_every_function_a_notebook_calls_is_named_for_its_stage(self):
        from mlmodels import MLMODELS_API
        from mlmodels._constants import NOTEBOOK_STAGES

        prefixes = tuple(f"{stage.lower()}_" for stage in NOTEBOOK_STAGES)
        self.assertTrue(MLMODELS_API)
        self.assertEqual([], [name for name in MLMODELS_API if name != "GateError" and not name.startswith(prefixes)])

    def test_flavours_splits_and_stages_agree(self):

        from mlmodels._constants import NOTEBOOK_STAGES, PROJECT_FLAVOURS, PROJECT_SPLITS

        flavours = re.findall(r"^\| `(\w+)` \|", self.section("### 3.2 Flavours"), re.MULTILINE)
        splits = re.findall(r"^\| `(\w+)` \|", self.section("### 6.3 Splits"), re.MULTILINE)
        stages = re.findall(r"^#### 6\.7\.\d+ ([A-Z][A-Za-z ]+)$", self.spec, re.MULTILINE)
        self.assertTrue(flavours and splits and stages)
        self.assertEqual(sorted(PROJECT_FLAVOURS), sorted(flavours))
        self.assertEqual(sorted(PROJECT_SPLITS), sorted(splits))
        self.assertEqual(list(NOTEBOOK_STAGES), stages)


def build_project(*arguments, **options):
    from mlmodels.testing import build_project as build

    return build(*arguments, **options)


def fresh_mlruns_dir():
    directory = join(ROOT, "rue/mlmodels/target/mlruns-test")
    shutil.rmtree(directory, ignore_errors=True)
    os.makedirs(directory)
    return directory


if __name__ == "__main__":
    unittest.main()
