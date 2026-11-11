import json
import math

from mlmodels._lint_project import verify_project
from mlmodels.runtime.loader import Model, Project, load, load_onnx, load_pyfunc, load_static, load_wasm, replay


def replay_project(project_dir):
    verify_project(project_dir)
    model = load(project_dir)
    return replay(project_dir, model.signature(), model.predict)


def load_model(model_path, flavour, signature, constants=None):
    loaders = {"wasm": load_wasm, "onnx": load_onnx, "pyfunc": load_pyfunc}
    driver = load_static(json.dumps(constants), json.dumps(signature)) if flavour == "static" else loaders[flavour](model_path, json.dumps(signature))
    integers = {entry["name"] for entry in signature["outputs"] if entry["datatype"] == "INT64"}

    def truncated(inputs):
        return {name: [math.trunc(value) if name in integers and math.isfinite(value) else value for value in values] for name, values in driver(inputs).items()}

    return Model(model_path, Project({"name": signature["name"], "flavour": flavour}, json.dumps(signature), ""), truncated).predict
