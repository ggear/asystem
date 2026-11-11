import json
import os
import sys
import tempfile
import unittest
import warnings
from os.path import abspath, dirname, join, realpath
from types import SimpleNamespace
from typing import Any
from unittest import mock

sys.path.append("../../../main/python")

import mlmodels._collect
from asystem.report import run_pytest
from mlmodels._errors import GateError
from mlmodels.workflow.collect import collect_run
from mlmodels.workflow.setup import setup_workspace

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))


class SetupWorkspaceTest(unittest.TestCase):
    def test_setup_workspace_reads_the_env_and_the_signature(self):
        ws = setup_workspace("example/static/constant")
        self.assertTrue(ws.env["MLFLOW_TRACKING_URI"].startswith("http"))
        self.assertEqual("example_static_constant", ws.model_name)
        self.assertEqual(["static_in"], ws.inputs)


class WorkspaceFieldsTest(unittest.TestCase):
    def test_a_workspace_takes_params_and_refuses_any_other_new_field(self):
        ws = setup_workspace("example/static/constant")
        self.assertEqual({}, ws.params)
        ws.params["gain"] = 2.5
        self.assertEqual({"gain": 2.5}, ws.params)
        with self.assertRaises(AttributeError):
            ws.training_pl = None


class CollectRunTest(unittest.TestCase):
    NAME = "demo_run"

    def setUp(self):
        self.ws = SimpleNamespace(
            path=join(tempfile.mkdtemp(), "demo"),
            runs={},
            model_name="homeassistant_demo_run",
            env={"INFLUXDB3_IP_PROD": "host", "INFLUXDB3_API_PORT": "1", "INFLUXDB3_TOKEN_ADMIN": "token", "INFLUXDB3_DATABASE_HOME": "home"},
        )

    def response(self, text, ok=True):
        return mock.Mock(ok=ok, status_code=200 if ok else 400, text=text)

    def query(self, post, query="SELECT 1", run=1000, **kwargs):
        with mock.patch.object(mlmodels._collect, "post", post):
            collect_run(self.ws, run, label="demo", source="influxdb3", query=query, **kwargs)
        return self.ws.runs[(run, kwargs.get("name", self.NAME))].frame

    def sidecar(self, run=1000):
        with open(join(self.ws.path, "data", str(run), f"{self.NAME}.json")) as sidecar_file:
            return json.load(sidecar_file)

    def test_a_query_is_captured_when_the_csv_is_absent_and_never_again(self):
        post = mock.Mock(return_value=self.response("time,value\n2026-01-01T00:00:00,1.5\n"))
        first = self.query(post)
        second = self.query(post)
        self.assertEqual(1, post.call_count)
        self.assertEqual(first.to_dicts(), second.to_dicts())
        self.assertEqual(1.5, first["value"][0])
        self.assertTrue(self.ws.runs[(1000, self.NAME)].path.endswith(f"data/1000/{self.NAME}.csv"))
        self.assertEqual(("influxdb3", "SELECT 1", 1), (self.sidecar()["source"], self.sidecar()["query"], self.sidecar()["rows"]))
        self.assertNotIn("split", self.sidecar())

    def test_a_live_run_is_captured_again_on_every_execution(self):
        self.query(mock.Mock(return_value=self.response("time,value\n2026-01-01T00:00:00,1.5\n")))
        self.assertFalse(self.ws.runs[(1000, self.NAME)].live)
        frame = self.query(mock.Mock(return_value=self.response("time,value\n2026-01-01T00:00:00,2.5\n")), live=True)
        self.assertEqual(2.5, frame["value"][0])
        self.assertTrue(self.ws.runs[(1000, self.NAME)].live)
        self.assertEqual(["1000"], os.listdir(join(self.ws.path, "data")))
        self.assertEqual(("demo", True), (self.sidecar()["label"], self.sidecar()["live"]))

    def test_a_run_without_a_label_fails(self):
        for label in (None, "", " "):
            with self.assertRaises(ValueError):
                collect_run(self.ws, 1000, label=label, source="builder", build=dict)

    def test_a_changed_query_over_a_cached_run_is_a_gate_error(self):
        self.query(mock.Mock(return_value=self.response("time,value\n2026-01-01T00:00:00,1.5\n")))
        with self.assertRaises(GateError):
            self.query(mock.Mock(), query="SELECT 2")

    def test_params_are_formatted_into_the_query_and_recorded(self):
        post = mock.Mock(return_value=self.response("time,value\n2026-01-01T00:00:00,1.5\n"))
        self.query(post, query="SELECT 1 WHERE time >= '{start}'", params={"start": "2026-01-01"})
        self.assertEqual("SELECT 1 WHERE time >= '2026-01-01'", self.sidecar()["query"])
        self.assertEqual({"start": "2026-01-01"}, self.sidecar()["params"])
        self.assertIn("2026-01-01", post.call_args.kwargs["json"]["q"])
        with self.assertRaises(GateError):
            self.query(mock.Mock(), query="SELECT 1 WHERE time >= '{start}'", params={"start": "2026-02-01"})

    def test_runs_are_numbered_directories(self):
        post = mock.Mock(return_value=self.response("time,value\n"))
        self.query(post, run=1000)
        self.query(post, run=1001)
        self.assertEqual(["1000", "1001"], sorted(os.listdir(join(self.ws.path, "data"))))

    def test_a_run_that_is_not_an_integer_from_1000_fails(self):
        for run in (0, 999, "1000", True):
            with self.assertRaises(ValueError):
                collect_run(self.ws, run, label="demo", source="builder", build=dict)

    def test_any_run_may_be_live_whatever_its_number(self):
        post = mock.Mock(return_value=self.response("time,value\n2026-01-01T00:00:00,1.5\n"))
        self.query(post, run=1000, live=True)
        self.query(post, run=1001)
        self.query(post, run=1000, live=True)
        self.assertEqual(3, post.call_count)

    def test_a_csv_with_no_json_is_an_interrupted_capture_and_is_refused(self):
        post = mock.Mock(return_value=self.response("time,value\n2026-01-01T00:00:00,1.5\n"))
        self.query(post)
        os.remove(join(self.ws.path, "data", "1000", f"{self.NAME}.json"))
        with self.assertRaises(GateError):
            self.query(post)

    def test_a_query_that_returns_no_rows_is_captured_as_an_empty_run(self):
        query = "SELECT time, CASE WHEN a > 1 THEN b END AS value, CAST(c AS DOUBLE) d\nFROM demo"
        frame = self.query(mock.Mock(return_value=self.response("")), query=query)
        self.assertEqual((0, 3), frame.shape)
        again = self.query(mock.Mock(), query=query)
        self.assertEqual(["time", "value", "d"], again.columns)
        self.assertEqual(0, self.sidecar()["rows"])

    def test_a_failed_query_writes_nothing(self):
        with self.assertRaises(RuntimeError):
            self.query(mock.Mock(return_value=self.response("bad", ok=False)))
        self.assertFalse(os.path.isdir(join(self.ws.path, "data")))

    def test_a_builder_runs_once_and_then_the_csv_is_read(self):
        builds = []

        def build():
            builds.append(1)
            return {"x": [1.0, 2.0]}

        collect_run(self.ws, 1000, label="demo", name="demo_run", source="builder", build=build)
        first = self.ws.runs[(1000, "demo_run")].frame
        collect_run(self.ws, 1000, label="demo", name="demo_run")
        second = self.ws.runs[(1000, "demo_run")].frame
        self.assertEqual(1, len(builds))
        self.assertEqual(first.to_dicts(), second.to_dicts())
        self.assertTrue(os.path.isfile(self.ws.runs[(1000, "demo_run")].path))

    def test_an_absent_dataset_without_a_source_is_an_error(self):
        with self.assertRaises(ValueError):
            collect_run(self.ws, 1000, label="demo")

    def test_a_csv_source_copies_the_file_into_the_run(self):
        source = join(tempfile.mkdtemp(), "in.csv")
        with open(source, "w") as source_file:
            source_file.write("a,b\n1,2\n")
        collect_run(self.ws, 1000, label="demo", source="csv", csv=source)
        frame = self.ws.runs[(1000, self.NAME)].frame
        self.assertEqual([{"a": 1, "b": 2}], frame.to_dicts())


class PrepareSplitTest(unittest.TestCase):
    def setUp(self):
        from mlmodels._workspace import Workspace

        self.ws = Workspace("demo/calc/run", join(tempfile.mkdtemp(), "run"), "", "demo_calc_run", {}, {}, [], [], "")
        for run in (1000, 1001, 1002):
            collect_run(
                self.ws,
                run,
                label="demo",
                source="builder",
                build=lambda run=run: {"time": [f"2026-01-0{run - 999}T00:0{step}:00" for step in range(6)], "value": [float((run - 999) * 10 + step) for step in range(6)]},
                live=run == 1002,
            )

    def test_splits_are_selections_of_runs_and_become_attributes(self):
        from mlmodels.workflow.prepare import prepare_split

        prepare_split(self.ws, training=self.ws.run(1000), validation=self.ws.run(1001)[:3], backtest=self.ws.run(1001)[3:], monitoring=self.ws.run(1002))
        self.assertEqual((6, 3, 3, 6), tuple(getattr(self.ws, name).height for name in ("training", "validation", "backtest", "monitoring")))
        self.assertEqual([20.0, 21.0, 22.0], self.ws.validation["value"].to_list())
        self.assertEqual([("data/1001", 3)], [(path.split("/run/")[1].rsplit("/", 1)[0], rows) for path, rows in self.ws.splits["validation"].paths])

    def test_a_fluent_selection_filters_by_time_head_and_expression(self):
        import polars as pl

        run = self.ws.run(1001)
        self.assertEqual(2, run.between("2026-01-02T00:01:00", "2026-01-02T00:03:00").frame.height)
        self.assertEqual(2, run.head(2).frame.height)
        self.assertEqual([24.0, 25.0], run.tail(2).frame["value"].to_list())
        self.assertEqual(3, run.filter(pl.col("value") > 22).frame.height)
        self.assertEqual(run.rows, run.head(10).rows)

    def test_splits_that_share_rows_must_declare_the_overlap(self):
        from mlmodels.workflow.prepare import prepare_split

        with self.assertRaises(GateError):
            prepare_split(self.ws, training=self.ws.run(1000), validation=self.ws.run(1000)[:2])
        prepare_split(self.ws, training=self.ws.run(1000), validation=self.ws.run(1000)[:2], overlap=[("validation", "training")])
        self.assertEqual(2, self.ws.validation.height)

    def test_a_backtest_may_not_share_rows_with_training_or_validation_even_when_declared(self):
        from mlmodels.workflow.prepare import prepare_split

        for other in ("training", "validation"):
            with self.assertRaises(GateError):
                prepare_split(self.ws, **{other: self.ws.run(1000), "backtest": self.ws.run(1000)[:2]}, overlap=[(other, "backtest")])
        prepare_split(self.ws, training=self.ws.run(1000), backtest=self.ws.run(1001))
        self.assertEqual(6, self.ws.backtest.height)

    def test_a_live_run_may_only_be_the_monitoring_split(self):
        from mlmodels.workflow.prepare import prepare_split

        with self.assertRaises(GateError):
            prepare_split(self.ws, training=self.ws.run(1002))
        prepare_split(self.ws, training=self.ws.run(1000), monitoring=self.ws.run(1002))
        self.assertEqual(6, self.ws.monitoring.height)

    def test_blocked_folds_hold_each_block_out_with_a_gap(self):
        from mlmodels.workflow.prepare import prepare_folds

        seen = []
        for fold in prepare_folds(self.ws, self.ws.run(1001), k=3, gap=1):
            seen.append((self.ws.training["value"].to_list(), self.ws.validation["value"].to_list()))
            fold.record(rmse=float(fold.index))
        self.assertEqual(
            [([23.0, 24.0, 25.0], [20.0, 21.0]), ([20.0, 25.0], [22.0, 23.0]), ([20.0, 21.0, 22.0], [24.0, 25.0])],
            seen,
        )
        self.assertEqual([0.0, 1.0, 2.0], [entry["rmse"] for entry in self.ws.folds])
        self.assertEqual((3, 1, "blocked"), (len(self.ws.folds), self.ws.folds[0]["gap"], self.ws.folds[0]["scheme"]))

    def test_forward_folds_only_train_on_earlier_rows(self):
        from mlmodels.workflow.prepare import prepare_folds

        for _ in prepare_folds(self.ws, self.ws.run(1001), k=3, scheme="forward"):
            self.assertLess(max(self.ws.training["time"].to_list()), min(self.ws.validation["time"].to_list()))
        self.assertEqual([1, 2], [entry["fold"] + 1 for entry in self.ws.folds])

    def test_folds_need_at_least_two_blocks_enough_rows_and_training_rows(self):
        from mlmodels.workflow.prepare import prepare_folds

        with self.assertRaises(ValueError):
            list(prepare_folds(self.ws, self.ws.run(1001), k=1))
        with self.assertRaises(ValueError):
            list(prepare_folds(self.ws, self.ws.run(1001), k=3, scheme="shuffled"))
        with self.assertRaises(GateError):
            list(prepare_folds(self.ws, self.ws.run(1001), k=7))
        with self.assertRaises(GateError):
            list(prepare_folds(self.ws, self.ws.run(1001), k=2, gap=3))

    def test_a_live_run_cannot_be_folded(self):
        from mlmodels.workflow.prepare import prepare_folds

        with self.assertRaises(GateError):
            list(prepare_folds(self.ws, self.ws.run(1002), k=2))

    def test_an_empty_or_unknown_split_fails(self):
        from mlmodels.workflow.prepare import prepare_split

        with self.assertRaises(GateError):
            prepare_split(self.ws, training=self.ws.run(1000).head(0))
        with self.assertRaises(ValueError):
            prepare_split(self.ws, testing=self.ws.run(1000))

    def test_a_split_that_is_not_defined_is_an_error_and_each_call_replaces_the_last(self):
        from mlmodels.workflow.prepare import prepare_split

        with self.assertRaises(AttributeError):
            _ = self.ws.training
        prepare_split(self.ws, training=self.ws.run(1000))
        prepare_split(self.ws, validation=self.ws.run(1001))
        with self.assertRaises(AttributeError):
            _ = self.ws.training


class ModelWorkspaceCase(unittest.TestCase):
    STATE = False

    def setUp(self):
        from mlmodels._signature import build_signature, signature_input, signature_output
        from mlmodels._workspace import Workspace
        from mlmodels.workflow.prepare import prepare_split

        inputs = [signature_input("demo_in_seconds", "seconds", "A time.")]
        outputs = [signature_output("demo_out_seconds", "seconds", "A time out.", datatype="FP64")]
        state = []
        if self.STATE:
            inputs.append(signature_input("demo_state_in", "state", "Carried state.", required=False, shape=[-1]))
            outputs.append(signature_output("demo_state_out", "state", "Next state.", datatype="FP64", required=False, shape=[-1]))
            state = [{"name": "total_seconds", "unit": "seconds", "description": "The running total."}]
        self.signature = build_signature("demo_calc_run", inputs, outputs, state=state)
        self.path = join(tempfile.mkdtemp(), "run")
        os.makedirs(self.path)
        with open(join(self.path, "notebook.ipynb"), "w") as notebook_file:
            json.dump({"cells": []}, notebook_file)
        self.ws = Workspace("demo/calc/run", self.path, "", "demo_calc_run", {}, self.signature, ["demo_in_seconds"], ["demo_out_seconds"], join(self.path, "scratch"))
        for run, split in ((1000, "training"), (1001, "validation")):
            collect_run(
                self.ws,
                run,
                label=split,
                name="calc_run",
                source="builder",
                build=lambda run=run: {"demo_in_seconds": [1.0, 2.0, 3.0], "demo_out_seconds": [2.5, 5.0, 7.5], "incumbent": [9.0, 9.0, 9.0 + run - 1000]},
            )
        prepare_split(self.ws, training=self.ws.run(1000), validation=self.ws.run(1001))

    def model_dirs(self):
        return sorted(os.listdir(join(self.path, "model"))) if os.path.isdir(join(self.path, "model")) else []


GAIN = 2.5


def linear(demo_in_seconds):
    return GAIN * demo_in_seconds


SCALE = 2.0


def reads_a_global(demo_in_seconds):
    return SCALE * demo_in_seconds


def optional_gain(demo_in_seconds, demo_gain):
    return demo_in_seconds if demo_gain is None else demo_in_seconds * demo_gain


SHIFT = 3.0


def traced_with_a_hidden_global(demo_in_seconds):
    return demo_in_seconds + SHIFT


class DefineModelTest(ModelWorkspaceCase):
    def define(self, model: Any = 1000, source=linear, **overrides):
        from mlmodels.workflow.define import define_model

        return define_model(self.ws, **{"model": model, "flavour": "pyfunc", "source": source, "label": "A line", "constants": {"GAIN": GAIN}, **overrides})

    def test_a_function_becomes_a_model_file_and_a_document_that_hash_each_other(self):
        from mlmodels._lint_project import file_sha256

        self.define()
        record = self.ws.models[1000]
        self.assertEqual([2.5, 5.0], [record.predict({"demo_in_seconds": [x]})["demo_out_seconds"][0] for x in (1.0, 2.0)])
        self.assertEqual(["1000"], self.model_dirs())
        with open(join(self.path, "model/1000/model.json")) as document_file:
            document = json.load(document_file)
        self.assertEqual((1000, "pyfunc", [1000], file_sha256(join(self.path, "model/1000/model.py"))), (document["model"], document["flavour"], document["runs"], document["sha256"]))
        with open(join(self.path, "model/1000/model.py")) as model_file:
            self.assertIn("GAIN = 2.5", model_file.read())

    def test_an_optional_input_the_request_omits_reaches_the_function_as_none(self):
        from mlmodels._model import model_content
        from mlmodels.runtime.loader import load_pyfunc

        stub = SimpleNamespace(inputs=["demo_in_seconds", "demo_gain"], outputs=["demo_out_seconds"])
        _, content, _ = model_content(stub, "pyfunc", optional_gain, {})
        with tempfile.TemporaryDirectory() as directory:
            with open(join(directory, "model.py"), "wb") as model_file:
                model_file.write(content or b"")
            predict = load_pyfunc(join(directory, "model.py"), json.dumps({"outputs": [{"name": "demo_out_seconds", "datatype": "FP64"}]}))
        self.assertEqual([3.0], predict({"demo_in_seconds": [3.0]})["demo_out_seconds"])
        self.assertEqual([6.0], predict({"demo_in_seconds": [3.0], "demo_gain": [2.0]})["demo_out_seconds"])

    def test_a_rerun_writes_the_same_bytes(self):
        self.define()
        first = self.ws.models.pop(1000).sha256
        self.define()
        self.assertEqual(first, self.ws.models[1000].sha256)

    def test_a_model_id_must_be_an_unused_integer_from_1000(self):
        for model in (999, True, "1000", 1000.0):
            with self.assertRaises(GateError):
                self.define(model=model)
        self.define()
        with self.assertRaises(GateError):
            self.define()

    def test_a_function_that_reads_a_global_which_is_not_a_constant_is_refused_and_leaves_no_directory(self):
        with self.assertRaises(GateError):
            self.define(source=reads_a_global)
        self.assertEqual([], self.model_dirs())
        self.assertEqual({}, self.ws.models)

    def test_outputs_that_differ_from_the_signature_are_refused_and_leave_no_directory(self):
        with self.assertRaises(GateError):
            self.define(flavour="static", source={"other_out": 1})
        self.assertEqual([], self.model_dirs())

    def test_a_traced_function_may_not_read_a_notebook_value_that_is_not_a_constant(self):
        with self.assertRaises(GateError):
            self.define(flavour="wasm", source=traced_with_a_hidden_global, constants={})
        self.define(flavour="wasm", source=traced_with_a_hidden_global, constants={"SHIFT": SHIFT})
        self.assertEqual([4.0], self.ws.models[1000].predict({"demo_in_seconds": [1.0]})["demo_out_seconds"])

    def test_a_lambda_is_not_a_source(self):
        with self.assertRaises(GateError):
            self.define(source=lambda demo_in_seconds: demo_in_seconds)

    def test_constants_that_are_not_plain_values_are_refused(self):
        with self.assertRaises(GateError):
            self.define(constants={"GAIN": object()})

    def test_a_constant_that_disagrees_with_the_notebook_is_refused_for_a_traced_function(self):
        with self.assertRaises(GateError):
            self.define(flavour="wasm", constants={"GAIN": 99.0})

    def test_two_pyfunc_models_in_one_process_do_not_interfere(self):
        self.define()
        self.define(model=1001, source=linear, constants={"GAIN": 10.0})
        self.assertEqual([2.5, 10.0], [self.ws.models[model].predict({"demo_in_seconds": [1.0]})["demo_out_seconds"][0] for model in (1000, 1001)])

    def test_a_static_model_keeps_its_constants_in_its_document_and_no_file(self):
        self.define(flavour="static", source={"demo_out_seconds": 7.0})
        self.assertEqual(["model.json"], sorted(os.listdir(join(self.path, "model/1000"))))
        self.assertEqual({"demo_out_seconds": 7.0}, self.ws.models[1000].constants)


class EvaluateModelTest(ModelWorkspaceCase):
    def test_predictions_keep_the_time_and_the_incumbent_and_leave_the_truth_in_the_split(self):
        from mlmodels.workflow.define import define_model
        from mlmodels.workflow.evaluate import evaluate_model

        define_model(self.ws, model=1000, flavour="pyfunc", source=linear, label="A line", constants={"GAIN": GAIN})
        scored = evaluate_model(self.ws, 1000, "validation")
        self.assertEqual(["demo_out_seconds", "incumbent"], scored.columns)
        self.assertEqual([2.5, 5.0, 7.5], scored["demo_out_seconds"].to_list())
        self.assertEqual([9.0, 9.0, 10.0], scored["incumbent"].to_list())

    def test_an_undefined_model_is_a_gate_error(self):
        from mlmodels.workflow.evaluate import evaluate_model

        with self.assertRaises(GateError):
            evaluate_model(self.ws, 1000, "validation")


class EvaluateStateTest(ModelWorkspaceCase):
    STATE = True

    def define_total(self):
        from mlmodels.workflow.define import define_model

        def total(demo_in_seconds, demo_total):
            return [demo_in_seconds + demo_total, demo_total + demo_in_seconds]

        define_model(self.ws, model=1000, flavour="wasm", source=total, label="A running total")

    def test_state_is_carried_through_a_split_in_row_order(self):
        from mlmodels.workflow.evaluate import evaluate_model

        self.define_total()
        self.assertEqual([1.0, 3.0, 6.0], evaluate_model(self.ws, 1000, "training")["demo_out_seconds"].to_list())

    def test_a_golden_carries_state_inside_a_sequence_and_resets_it_where_the_sequence_changes(self):
        from mlmodels.workflow.evaluate import evaluate_gate
        from mlmodels.workflow.package import package_model

        self.define_total()
        evaluate_gate(self.ws, 1000, lambda: [{"split": "validation", "output": "demo_out_seconds", "name": "rmse", "value": 0.0, "limit": 1.0, "direction": "max"}])
        golden = {"demo_in_seconds": [1.0, 2.0, 3.0, 10.0, 20.0, None], "sequence": ["a", "a", "a", "b", "b", "b"], "expect": ["ok"] * 5 + ["error"]}
        package_model(self.ws, 1000, golden, target={"kind": "served"})
        with open(join(self.ws.project_dir, "golden.json")) as golden_file:
            document = json.load(golden_file)
        totals = {sequence["name"]: [step["response"]["outputs"][0]["data"][0] for step in sequence["steps"] if "response" in step] for sequence in document["sequences"]}
        self.assertEqual({"a": [1.0, 3.0, 6.0], "b": [10.0, 30.0]}, totals)

    def test_a_check_that_could_not_be_measured_fails_and_the_run_continues(self):
        from mlmodels.workflow.evaluate import evaluate_gate

        self.define_total()
        evaluation = evaluate_gate(self.ws, 1000, lambda: [{"split": "validation", "output": "demo_out_seconds", "name": "rmse", "value": None, "limit": 1.0, "direction": "max"}])
        self.assertEqual((False, None), (evaluation["passed"], evaluation["budget"]))


class PackageModelTest(ModelWorkspaceCase):
    def define(self, source=linear):
        from mlmodels.workflow.define import define_model

        define_model(self.ws, model=1000, flavour="pyfunc", source=source, label="A line", constants={"GAIN": GAIN})

    def gate(self, limit):
        from mlmodels.workflow.evaluate import evaluate_gate

        evaluate_gate(self.ws, 1000, lambda: [{"split": "validation", "output": "demo_out_seconds", "name": "rmse", "value": 1.0, "limit": limit, "direction": "max"}])

    def test_registration_records_params_dataset_schema_figures_tables_and_a_description(self):
        import mlflow
        from mlmodels.workflow.evaluate import evaluate_plot
        from mlmodels.workflow.register import register_model

        self.define()
        self.gate(1.0)
        evaluate_plot(self.ws, [1000], "validation")
        self.package()
        uri = f"sqlite:///{join(tempfile.mkdtemp(), 'mlflow.db')}"
        self.ws.env["MLFLOW_TRACKING_URI"] = uri
        register_model(self.ws, 1000)
        mlflow.set_tracking_uri(uri)
        run = mlflow.search_runs(experiment_names=["demo_calc_run"], output_format="list")[0]
        self.assertEqual(("1000", "A line", "3"), (run.data.params["model"], run.data.params["label"], run.data.params["rows.training"]))
        self.assertEqual("2.5", run.data.params["constant.GAIN"])
        assert run.inputs is not None
        self.assertIn("demo_in_seconds", str(run.inputs.dataset_inputs[0].dataset.schema))
        client = mlflow.MlflowClient()
        self.assertEqual({"figures", "evaluation"} <= {entry.path for entry in client.list_artifacts(run.info.run_id)}, True)
        self.assertIn("demo_out_seconds", str(client.get_model_version_by_alias("demo_calc_run", "preview").description))

    def package(self, golden=None, model=1000):
        from mlmodels.workflow.package import package_model

        package_model(self.ws, model, golden or {"demo_in_seconds": [1.0, None], "expect": ["ok", "error"]}, target={"kind": "served"})
        with open(join(self.ws.project_dir, "project.json")) as manifest_file:
            return json.load(manifest_file)

    def test_a_gated_model_is_packaged_with_its_id_and_a_byte_identical_model_file(self):
        from mlmodels._lint_project import file_sha256

        self.define()
        self.gate(2.0)
        manifest = self.package()
        self.assertEqual(1000, manifest["model_id"])
        self.assertEqual(file_sha256(join(self.path, "model/1000/model.py")), file_sha256(join(self.ws.project_dir, "model.py")))
        with open(join(self.path, "metadata.json")) as metadata_file:
            self.assertEqual({"kind": "served"}, json.load(metadata_file)["target"])

    def test_a_model_with_no_gate_result_is_not_packaged(self):
        self.define()
        with self.assertRaises(GateError):
            self.package()

    def test_a_model_whose_gate_failed_is_not_packaged(self):
        self.define()
        self.gate(0.5)
        with self.assertRaises(GateError):
            self.package()

    def test_a_model_directory_this_run_did_not_define_is_not_packaged(self):
        self.define()
        self.gate(2.0)
        os.makedirs(join(self.path, "model/1005"))
        with self.assertRaises(GateError):
            self.package()

    def test_an_error_row_that_supplies_every_required_input_is_refused(self):
        self.define()
        self.gate(2.0)
        with self.assertRaises(GateError):
            self.package({"demo_in_seconds": [1.0], "expect": ["error"]})

    def test_an_ok_row_missing_a_required_input_is_refused(self):
        self.define()
        self.gate(2.0)
        with self.assertRaises(GateError):
            self.package({"demo_in_seconds": [None], "expect": ["ok"]})

    def test_a_static_model_needs_no_gate(self):
        from mlmodels.workflow.define import define_model

        define_model(self.ws, model=1000, flavour="static", source={"demo_out_seconds": 7.0}, label="Seven")
        self.assertEqual("static", self.package()["flavour"])

    def test_register_refuses_a_model_that_was_not_packaged(self):
        from mlmodels.workflow.register import register_model

        self.define()
        self.gate(2.0)
        self.package()
        with self.assertRaises(GateError):
            register_model(self.ws, 1001)


class ExplorePlotTest(unittest.TestCase):
    def test_each_plot_starts_a_figure_unless_it_overlays_the_last(self):
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import polars as pl

        from mlmodels.workflow.explore import explore_plot

        frame = pl.DataFrame({"x": [1.0, 2.0], "y": [3.0, 4.0]})
        plt.close("all")
        explore_plot("one", frame, "x", "y")
        explore_plot("two", frame, "x", "y")
        explore_plot("overlay", frame, "x", "y", "o", overlay=True)
        self.assertEqual(2, len(plt.get_fignums()))
        self.assertEqual(2, len(plt.gcf().axes[0].lines))
        plt.close("all")


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
        from mlmodels._wasm import const, feature, var, wasm_build
        from mlmodels.maths import add, mul

        built = wasm_build(2, [var("out"), add(feature(1), var("out"))], lets=[("out", add(mul(feature(0), const(2.5)), const(1.0)))])
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
        from mlmodels._wasm import const, feature, wasm_build
        from mlmodels.maths import lt, select

        built = wasm_build(1, [select(lt(feature(0), const(20.0)), const(1.0), const(2.0))])
        self.assertEqual([[1.0], [2.0], [2.0]], self.run_module(built, [[19.5], [20.0], [30.0]], 1))

    def test_a_maths_function_is_imported_and_runs_through_the_python_hosts(self):
        import math

        from mlmodels._replay import load_model as evaluate_predict
        from mlmodels._signature import build_signature, signature_input, signature_output
        from mlmodels._wasm import const, feature, wasm_build
        from mlmodels.maths import add, atan, exp, log, mul, tanh

        built = wasm_build(1, [add(mul(atan(feature(0)), const(2.0)), const(1.0)), exp(feature(0)), log(feature(0)), tanh(feature(0))])
        path = join(tempfile.mkdtemp(), "model.wasm")
        with open(path, "wb") as model_file:
            model_file.write(built)
        signature = build_signature(
            "demo_calc",
            [signature_input("demo_in_seconds", "seconds", "Input.")],
            [signature_output(name, "seconds", "Output.", datatype="FP64") for name in ("demo_a_seconds", "demo_b_seconds", "demo_c_seconds", "demo_d_seconds")],
        )
        predict = evaluate_predict(path, "wasm", signature)
        for value in (0.0, 0.5, 3.25, -2.0):
            answer = predict({"demo_in_seconds": [value]})
            self.assertEqual(math.atan(value) * 2.0 + 1.0, answer["demo_a_seconds"][0])
            self.assertEqual(math.exp(value), answer["demo_b_seconds"][0])
            self.assertEqual(math.tanh(value), answer["demo_d_seconds"][0])
        self.assertEqual(float("-inf"), predict({"demo_in_seconds": [0.0]})["demo_c_seconds"][0])
        self.assertTrue(math.isnan(predict({"demo_in_seconds": [-1.0]})["demo_c_seconds"][0]))
        self.assertEqual(float("inf"), predict({"demo_in_seconds": [1000.0]})["demo_b_seconds"][0])

    def predictor(self, built, names):
        from mlmodels._replay import load_model as evaluate_predict
        from mlmodels._signature import build_signature, signature_input, signature_output

        path = join(tempfile.mkdtemp(), "model.wasm")
        with open(path, "wb") as model_file:
            model_file.write(built)
        signature = build_signature("demo_calc", [signature_input("demo_in_seconds", "seconds", "Input.")], [signature_output(name, "seconds", "Output.", datatype="FP64") for name in names])
        return evaluate_predict(path, "wasm", signature)

    def test_a_traced_function_gives_the_same_answers_as_a_plain_call_and_as_the_module(self):
        import math

        import numpy

        from mlmodels._wasm import wasm_build, wasm_trace
        from mlmodels.maths import atan, clip, floor, select

        def capacity(voltage, scale, width, centre, offset):
            raw = scale * atan(width * (voltage - centre)) + offset
            return select(voltage < 3.0, 0.0, select(voltage > 3.9, 100.0, floor(clip(raw, 0.0, 100.0) / 5.0) * 5.0))

        outputs = wasm_trace(lambda voltage: capacity(voltage, 40.5, 9.5, 3.76, 56.7), 1)
        predict = self.predictor(wasm_build(1, outputs), ["demo_out_seconds"])
        for value in (*numpy.linspace(2.5, 4.2, 60).tolist(), 3.0, 3.9, float("inf"), float("-inf")):
            expected = capacity(value, 40.5, 9.5, 3.76, 56.7)
            self.assertEqual(expected, predict({"demo_in_seconds": [value]})["demo_out_seconds"][0], value)
        self.assertTrue(math.isnan(predict({"demo_in_seconds": [float("nan")]})["demo_out_seconds"][0]))
        self.assertEqual([capacity(value, 40.5, 9.5, 3.76, 56.7) for value in (2.0, 3.5, 4.0)], numpy.asarray(capacity(numpy.array([2.0, 3.5, 4.0]), 40.5, 9.5, 3.76, 56.7)).tolist())

    def test_operators_build_the_same_tree_as_the_helpers(self):
        from mlmodels._wasm import const, wasm_build, wasm_trace
        from mlmodels.maths import absolute, add, div, mul, neg, power, sub

        by_operators = wasm_trace(lambda x: [2.0 * x + 1.0 - x / 4.0, -x, x**3, 2.0**x, abs(x) + (1.0 - x)], 1)
        by_helpers = wasm_trace(lambda x: [sub(add(mul(const(2.0), x), const(1.0)), div(x, const(4.0))), neg(x), mul(mul(x, x), x), power(const(2.0), x), add(absolute(x), sub(const(1.0), x))], 1)
        self.assertEqual([entry.node for entry in by_helpers], [entry.node for entry in by_operators])
        names = ["a_seconds", "b_seconds", "c_seconds", "d_seconds", "e_seconds"]
        answer = self.predictor(wasm_build(1, by_operators), names)({"demo_in_seconds": [3.0]})
        self.assertEqual([6.0 + 1.0 - 0.75, -3.0, 27.0, 8.0, 3.0 + -2.0], [answer[name][0] for name in names])

    def test_a_traced_function_may_return_several_outputs_and_take_several_features(self):
        from mlmodels._wasm import wasm_build, wasm_trace

        def accumulate(x, total):
            out = 2.5 * x + 1.0
            return out, total + out

        outputs = wasm_trace(accumulate, 2)
        self.assertEqual(2, len(outputs))
        answer = self.run_module(wasm_build(2, outputs), [[2.0, 10.0], [0.0, 0.0]], 2)
        self.assertEqual([[6.0, 16.0], [1.0, 1.0]], answer)

    def test_an_expression_refuses_python_control_flow_and_numpy_functions(self):
        from typing import Any

        import numpy

        from mlmodels._wasm import feature

        x: Any = feature(0)
        with self.assertRaises(TypeError):
            bool(x < 1.0)
        with self.assertRaises(TypeError):
            numpy.arctan(x)
        with self.assertRaises(TypeError):
            self.assertIsNone(x + "1")

    def test_every_maths_function_agrees_with_numpy_at_the_edges_of_its_domain(self):
        import math

        from mlmodels import _wasm as wasm
        from mlmodels._constants import WASM_MATH_FUNCTIONS
        from mlmodels._wasm import wasm_build

        edges = [0.0, -0.0, 0.5, -0.5, 1.0, -1.0, 2.0, -3.0, 710.0, -710.0, 1000.0, -1000.0, float("inf"), float("-inf"), float("nan")]
        rights = [-1.0, -2.0, 0.5, 2.0, 3.0, 1e300]
        for name, arity in WASM_MATH_FUNCTIONS.items():
            function = getattr(wasm, "power" if name == "pow" else name)
            for right in rights if arity == 2 else [None]:
                arguments = [wasm.feature(0), wasm.const(right)] if arity == 2 else [wasm.feature(0)]
                predict = self.predictor(wasm_build(1, [function(*arguments)]), ["demo_out_seconds"])
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
        from mlmodels._wasm import wasm_build

        with self.assertRaises(ValueError):
            wasm_build(1, [("x", 1)])
        with self.assertRaises(ValueError):
            wasm_build(1, [("var", "missing")])
        with self.assertRaises(ValueError):
            wasm_build(1, [("const", float("nan"))])
        with self.assertRaises(ValueError):
            wasm_build(1, [("cbrt", ("x", 0))])
        with self.assertRaises(ValueError):
            wasm_build(1, [("pow", ("x", 0))])


class ScratchProjectDirTest(unittest.TestCase):
    def test_a_run_without_an_output_directory_gets_a_temporary_project(self):
        from mlmodels._workspace import scratch_project_dir

        with mock.patch.dict(os.environ, {"MODEL_OUTPUT_DIR": ""}):
            self.assertTrue(scratch_project_dir("demo/calc/run").endswith("/project"))

    def test_a_run_with_an_output_directory_gets_a_fresh_project_under_it(self):
        from mlmodels._workspace import scratch_project_dir

        output_dir = tempfile.mkdtemp()
        stale = join(output_dir, "project", "demo/calc/run")
        os.makedirs(stale)
        open(join(stale, "old.json"), "w").close()
        self.assertEqual(stale, scratch_project_dir("demo/calc/run", output_dir))
        self.assertFalse(os.path.exists(stale))


class ReplayRunnerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import subprocess

        env_fab = join(DIR_ROOT, "../../../.env_fab")
        script = (
            f". {env_fab} && export CARGO_HOME=$HOME/.rust/versions/asystem RUSTUP_HOME=$HOME/.rust/versions/asystem PATH=$HOME/.rust/versions/asystem/bin:$PATH "
            f"CARGO_TARGET_DIR={DIR_ROOT}/target/rust && (cd {DIR_ROOT}/src/main/rust/mlmodels && cargo build --quiet) && "
            f'(cd {DIR_ROOT}/src/main/go/mlmodels && "$GOROOT/bin/go" build -o {DIR_ROOT}/target/go/consumer .)'
        )
        build = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=900, check=False)
        cls.native = {"rust": join(DIR_ROOT, "target/rust/debug/consumer"), "go": join(DIR_ROOT, "target/go/consumer")}
        cls.runners = {**{host: [path] for host, path in cls.native.items()}, "python": [sys.executable, "-m", "mlmodels.runtime"]}
        if build.returncode != 0 or not all(os.path.isfile(path) for path in cls.native.values()):
            raise unittest.SkipTest(f"the Rust and Go consumers could not be built [{build.stderr.strip()[-200:]}]")

    def project(self, flavour, model_bytes=None, samples=None, tolerance=None):
        import wasmtime

        from mlmodels._project import evaluation_build, package_project
        from mlmodels._signature import build_signature, signature_input, signature_output

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
            evaluation = evaluation_build(lambda: [{"split": "backtest", "output": "demo_out", "name": "rmse", "value": 0.0, "limit": 1, "direction": "max"}], {"backtest": [dataset]})
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

        from mlmodels._lint_project import file_sha256

        golden_path = join(project_dir, "golden.json")
        with open(golden_path) as golden_file:
            golden = json.load(golden_file)
        change(golden)
        with open(golden_path, "w") as golden_file:
            json.dump(golden, golden_file)
        manifest_path = join(project_dir, "project.json")
        with open(manifest_path) as manifest_file:
            manifest = json.load(manifest_file)
        manifest["files"]["golden.json"] = file_sha256(golden_path)
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

        from mlmodels._wasm import feature, wasm_build
        from mlmodels.maths import atan

        samples = [{"demo_in": 1.5, "demo_out": math.atan(1.5)}, {"demo_in": 2.0, "demo_out": math.atan(2.0)}, {"demo_in": None, "expect": "error"}]
        project_dir = self.project("wasm", model_bytes=wasm_build(1, [atan(feature(0))]), samples=samples, tolerance={"demo_out": {"absolute": 1e-12}})
        for host in self.runners:
            completed = self.run_runner(host, project_dir)
            self.assertEqual(0, completed.returncode, f"{host} {completed.stderr}")

    def test_each_runner_provides_every_maths_function_within_a_stated_tolerance(self):
        from mlmodels import _wasm as wasm
        from mlmodels._constants import WASM_MATH_FUNCTIONS
        from mlmodels._wasm import wasm_build

        for name, arity in WASM_MATH_FUNCTIONS.items():
            function = getattr(wasm, "power" if name == "pow" else name)
            tree = function(wasm.feature(0), wasm.const(1.5)) if arity == 2 else function(wasm.feature(0))
            samples = [{"demo_in": value, "demo_out": function(value, 1.5) if arity == 2 else function(value)} for value in (0.25, 0.5, 0.9)]
            project_dir = self.project("wasm", model_bytes=wasm_build(1, [tree]), samples=[*samples, {"demo_in": None, "expect": "error"}], tolerance={"demo_out": {"absolute": 1e-12}})
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


class PyfuncLoaderTest(unittest.TestCase):
    HEAD = "import pandas as pd\nimport warnings\nfrom mlflow.models import set_model\nfrom mlflow.pyfunc import PythonModel\n"
    BODY = "\n\nclass Model(PythonModel):\n    def predict(self, context, model_input, params=None):\n        return pd.DataFrame({'y': [1.0 for _ in model_input['x']]})\n\n\nset_model(Model())\n"

    def load(self, extra=""):
        from mlmodels.runtime.loader import load_pyfunc

        path = join(tempfile.mkdtemp(), "model.py")
        with open(path, "w") as model_file:
            model_file.write(self.HEAD + extra + self.BODY)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            predict = load_pyfunc(path, json.dumps({"outputs": [{"name": "y", "datatype": "FP64"}]}))
        return predict, [str(warning.message) for warning in caught]

    def test_a_model_without_type_hints_loads_without_the_mlflow_warning_and_predicts(self):
        predict, messages = self.load()
        self.assertEqual({"y": [1.0]}, predict({"x": [3.0]}))
        self.assertEqual([], [message for message in messages if "type hint" in message])

    def test_any_other_warning_of_the_model_is_still_raised(self):
        _, messages = self.load("warnings.warn('keep this one')\n")
        self.assertEqual(["keep this one"], [message for message in messages if "keep" in message])


class ConsumerSourceTest(unittest.TestCase):
    def test_every_host_provides_exactly_the_maths_functions_of_the_spec(self):
        import re

        from mlmodels._constants import WASM_MATH_FUNCTIONS

        def read(path):
            with open(join(DIR_ROOT, path)) as source_file:
                return source_file.read()

        go = {name: 2 if name in ("atan2", "pow") else 1 for name in re.findall(r'"(\w+)": math\.', read("src/main/go/mlmodels/runtime/loader.go"))}
        rust_source = read("src/main/rust/mlmodels/src/runtime/loader.rs")
        rust = {
            name: arity
            for arity, kind in ((1, "unary"), (2, "binary"))
            for name in re.findall(r'\("(\w+)", f64::\w+\)', rust_source.split(f"let {kind}:")[1].split("];")[0] if kind == "unary" else rust_source.split(f"let {kind}:")[1].split(";\n")[0])
        }
        python = dict(re.findall(r'"(\w+)": (\d)', read("src/main/python/mlmodels/runtime/loader.py").split("arities = ")[1].split("}")[0]))
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

        from mlmodels.runtime.__main__ import main

        line = r"    (verify|load|replay)\s+ \.\.\. done \[[^\]]+\] \(\d+\.\d\ds\)"
        project = join(DIR_ROOT, "src/main/notebook/example/static/constant/project")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, main([project]))
        matches = [re.fullmatch(line, entry) for entry in output.getvalue().splitlines()]
        self.assertEqual(["verify", "load", "replay"], [match.group(1) for match in matches if match])
        self.assertEqual(3, len(matches))
        for path, forms in (
            ("src/main/go/mlmodels/main.go", ('report("verify"', 'report("load"', 'report("replay"', '"    %-12s ... done [%s] (%.2fs)\\n"')),
            ("src/main/rust/mlmodels/src/main.rs", ('report("verify"', 'report("load"', 'report("replay"', '"    {stage:<12} ... done [{detail}] ({:.2}s)"')),
        ):
            with open(join(DIR_ROOT, path)) as source_file:
                source = re.sub(r"\s+", "", source_file.read())
            for form in forms:
                self.assertIn(re.sub(r"\s+", "", form), source, path)


if __name__ == "__main__":
    sys.exit(run_pytest("mlmodels/unittest", ["-s", "-o", f"cache_dir={join(DIR_ROOT, 'target/.pytest_cache')}", __file__, join(dirname(__file__), "library_test.py")]))
