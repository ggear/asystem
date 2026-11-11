import os
import tempfile
import textwrap
from os.path import dirname, join

from mlmodels._constants import PROJECT_MODEL_FILES


def fixture_project(flavour, golden_out=None, tolerance=None):
    from mlmodels._project import evaluation_build, package_project
    from mlmodels._signature import build_signature, signature_input, signature_output

    work_dir = tempfile.mkdtemp()
    model_path = join(work_dir, PROJECT_MODEL_FILES[flavour])
    if flavour == "pyfunc":
        with open(model_path, "w") as model_file:
            model_file.write(
                textwrap.dedent(
                    """
                    import pandas as pd
                    from mlflow.models import set_model
                    from mlflow.pyfunc import PythonModel


                    class Double(PythonModel):
                        def predict(self, context, model_input: pd.DataFrame, params=None):
                            return pd.DataFrame({"demo_out": [x * 2.0 for x in model_input["demo_in"]]})


                    set_model(Double())
                    """
                )
            )
    elif flavour == "wasm":
        import wasmtime

        wat = '(module (memory (export "memory") 1) (func (export "predict") (param i32 i32 i32) (f64.store (local.get 2) (f64.mul (f64.load (local.get 0)) (f64.const 2)))))'
        with open(model_path, "wb") as model_file:
            model_file.write(wasmtime.wat2wasm(wat))
    else:
        import numpy
        import onnx
        from onnx import TensorProto, helper, numpy_helper

        graph = helper.make_graph(
            [helper.make_node("Mul", ["demo_in", "two"], ["demo_out"])],
            "double",
            [helper.make_tensor_value_info("demo_in", TensorProto.DOUBLE, [1, 1])],
            [helper.make_tensor_value_info("demo_out", TensorProto.DOUBLE, [1, 1])],
            initializer=[numpy_helper.from_array(numpy.array(2.0, dtype=numpy.float64), "two")],
        )
        model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 21)])
        model.ir_version = 10
        onnx.save(model, model_path)
    signature = build_signature("demo_replay_double", [signature_input("demo_in", "none", "A number.")], [signature_output("demo_out", "none", "Twice the number.", datatype="FP64")])
    dataset = join(work_dir, "2026-11-03_10-00-00", "demo_replay_backtest_2026-11-01_2026-11-02.csv")
    os.makedirs(dirname(dataset))
    with open(dataset, "w") as dataset_file:
        dataset_file.write("a,b\n1,2\n")
    evaluation = evaluation_build(lambda: [{"split": "backtest", "output": "demo_out", "name": "rmse", "value": 0.0, "limit": 1, "direction": "max"}], {"backtest": [dataset]})
    samples = [
        {"demo_in": 1.5, "demo_out": 3.0 if golden_out is None else golden_out},
        {"demo_in": -2.0, "demo_out": -4.0},
        {"demo_in": None, "expect": "error"},
    ]
    project_dir = join(work_dir, "project")
    package_project(
        project_dir,
        "demo_replay_double",
        flavour,
        signature,
        samples,
        {"source": "manual", "inputs": [], "implementation": "demo built by hand"},
        model_path=model_path,
        evaluation=evaluation,
        tolerance=tolerance,
    )
    return project_dir
