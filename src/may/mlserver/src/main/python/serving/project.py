import hashlib
import importlib.util
import json
import struct
from os.path import isfile, join
from unittest import mock

WASM_FUEL = 1_000_000
WASM_MEMORY_BYTES = 1 << 20


class Project:
    def __init__(self, directory, manifest, signature):
        self.directory = directory
        self.manifest = manifest
        self.signature = signature
        self.name = manifest["name"]
        self.version = str(manifest["model_version"])
        self._predict = None

    def predict(self, inputs):
        required = {entry["name"] for entry in self.signature["inputs"] if entry["parameters"]["required"]}
        if not required <= inputs.keys():
            raise ValueError(f"missing required inputs [{sorted(required - inputs.keys())}]")
        if self._predict is None:
            if self.manifest["flavor"] == "static":
                constants = {name: [value] for name, value in self.manifest["constants"].items()}
                self._predict = lambda _inputs: dict(constants)
            else:
                path = join(self.directory, self.manifest["files"]["model"]["path"])
                loaders = {"wasm": _wasm_predict, "onnx": _onnx_predict, "pyfunc": _pyfunc_predict}
                self._predict = loaders[self.manifest["flavor"]](path, self.signature)
        return self._predict(inputs)


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
        digest = hashlib.sha256()
        with open(path, "rb") as file:
            for chunk in iter(lambda: file.read(1 << 20), b""):
                digest.update(chunk)
        if digest.hexdigest() != entry["sha256"]:
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
