import hashlib
import importlib.util
import json
import struct
from os.path import isfile, join
from unittest import mock

WASM_FUEL = 1_000_000
WASM_MEMORY_BYTES = 1 << 20
RUNTIME = "project_runtime.runtime.ProjectRuntime"
SETTINGS_FILE = "model-settings.json"
SERVER_SETTINGS = {"host": "0.0.0.0", "http_port": 8080, "grpc_port": 8081, "parallel_workers": 0}


class Project:
    def __init__(self, directory, manifest, signature):
        self.directory = directory
        self.manifest = manifest
        self.signature = signature
        self.name = manifest["name"]
        self.version = str(manifest["model_version"])
        self._predict = None

    def predict(self, inputs):
        if self._predict is None:
            self._predict = _loader(self)
        required = {entry["name"] for entry in self.signature["inputs"] if entry["parameters"]["required"]}
        if not required <= inputs.keys():
            raise ValueError(f"missing required inputs {sorted(required - inputs.keys())}")
        return self._predict(inputs)

    def settings(self):
        return {
            "name": self.name,
            "implementation": RUNTIME,
            "parameters": {"version": self.version},
            "inputs": [_metadata(entry) for entry in self.signature["inputs"]],
            "outputs": [_metadata(entry) for entry in self.signature["outputs"]],
        }


def load_project(directory):
    manifest_path = join(directory, "project.json")
    if not isfile(manifest_path):
        raise ValueError(f"manifest missing [{manifest_path}]")
    with open(manifest_path) as manifest_file:
        manifest = json.load(manifest_file)
    for key, entry in manifest["files"].items():
        path = join(directory, entry["path"])
        if not isfile(path):
            raise ValueError(f"file absent [{key}] path [{entry['path']}]")
        if _sha256(path) != entry["sha256"]:
            raise ValueError(f"file checksum mismatch [{key}] path [{entry['path']}]")
    if manifest["flavor"] != "static" and "evaluation" not in manifest["files"]:
        raise ValueError(f"no acceptance evaluation for flavor [{manifest['flavor']}]")
    if "evaluation" in manifest["files"]:
        with open(join(directory, manifest["files"]["evaluation"]["path"])) as evaluation_file:
            if json.load(evaluation_file).get("passed") is not True:
                raise ValueError("acceptance not passed")
    with open(join(directory, manifest["files"]["signature"]["path"])) as signature_file:
        signature = json.load(signature_file)
    return Project(directory, manifest, signature)


def write_settings(directory, project):
    with open(join(directory, SETTINGS_FILE), "w") as settings_file:
        json.dump(project.settings(), settings_file, indent=2, sort_keys=True)
        settings_file.write("\n")


def write_server_settings(models_dir):
    with open(join(models_dir, "settings.json"), "w") as settings_file:
        json.dump(SERVER_SETTINGS, settings_file, indent=2, sort_keys=True)
        settings_file.write("\n")


def _loader(project):
    manifest = project.manifest
    if manifest["flavor"] == "static":
        constants = {name: [value] for name, value in manifest["constants"].items()}
        return lambda _inputs: dict(constants)
    path = join(project.directory, manifest["files"]["model"]["path"])
    if manifest["flavor"] == "wasm":
        return _wasm_predict(path, project.signature)
    if manifest["flavor"] == "onnx":
        return _onnx_predict(path, project.signature)
    return _pyfunc_predict(path, project.signature)


def _wasm_predict(path, signature):
    import wasmtime

    state_in = [entry for entry in signature["inputs"] if entry["shape"] == [-1]]
    state_slots = len(signature["parameters"].get("state", []))
    scalars_in = [entry for entry in signature["inputs"] if entry["shape"] != [-1]]
    outputs = signature["outputs"]
    config = wasmtime.Config()
    config.consume_fuel = True
    engine = wasmtime.Engine(config)
    module = wasmtime.Module.from_file(engine, path)

    def predict(inputs):
        store = wasmtime.Store(engine)
        store.set_fuel(WASM_FUEL)
        store.set_limits(memory_size=WASM_MEMORY_BYTES)
        instance = wasmtime.Instance(store, module, [])
        exports = instance.exports(store)
        memory = exports["memory"]
        function = exports["predict"]
        assert isinstance(memory, wasmtime.Memory) and isinstance(function, wasmtime.Func)
        row = [float(inputs[entry["name"]][0]) if entry["name"] in inputs else float("nan") for entry in scalars_in]
        for entry in state_in:
            row.extend(float(value) for value in inputs.get(entry["name"], [0.0] * state_slots))
        features = len(row)
        y_ptr = features * 8
        memory.write(store, struct.pack(f"<{features}d", *row), 0)
        function(store, 0, 1, y_ptr)
        width = sum(1 if entry["shape"] != [-1] else state_slots for entry in outputs)
        values = struct.unpack(f"<{width}d", memory.read(store, y_ptr, y_ptr + width * 8))
        result, position = {}, 0
        for entry in outputs:
            count = state_slots if entry["shape"] == [-1] else 1
            chunk = values[position : position + count]
            result[entry["name"]] = [int(value) for value in chunk] if entry["datatype"] == "INT64" else list(chunk)
            position += count
        return result

    return predict


def _onnx_predict(path, signature):
    import numpy
    import onnxruntime

    session = onnxruntime.InferenceSession(path, providers=["CPUExecutionProvider"])
    outputs = signature["outputs"]

    def predict(inputs):
        feeds = {entry["name"]: numpy.array([inputs[entry["name"]]], dtype=numpy.float64) for entry in signature["inputs"] if entry["name"] in inputs}
        values = session.run([entry["name"] for entry in outputs], feeds)
        return {entry["name"]: [int(item) if entry["datatype"] == "INT64" else float(item) for item in numpy.asarray(value).flatten()] for entry, value in zip(outputs, values, strict=True)}

    return predict


def _pyfunc_predict(path, signature):
    import pandas
    from mlflow.models import model as mlflow_model
    from mlflow.pyfunc.utils import data_validation

    spec = importlib.util.spec_from_file_location("project_model", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with mock.patch.object(data_validation, "color_warning"):
        spec.loader.exec_module(module)
    instance = getattr(mlflow_model, "__mlflow_model__")  # noqa: B009
    outputs = signature["outputs"]

    def predict(inputs):
        result = instance.predict(None, pandas.DataFrame(dict(inputs)))
        return {entry["name"]: [int(item) if entry["datatype"] == "INT64" else float(item) for item in result[entry["name"]]] for entry in outputs}

    return predict


def _metadata(entry):
    return {"name": entry["name"], "datatype": entry["datatype"], "shape": entry["shape"]}


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()
