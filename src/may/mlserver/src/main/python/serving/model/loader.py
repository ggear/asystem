################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

import hashlib
import json
import math
from os.path import isfile, join
from typing import NamedTuple


class ModelError(Exception):
    def __init__(self, kind, gate, cause):
        super().__init__(f"{kind} {gate} [{cause}]")
        self.kind = kind
        self.gate = gate
        self.cause = cause


class Info(NamedTuple):
    name: str
    flavour: str
    content_sha256: str
    model_id: int | None
    signature_version: int | None
    release_version: str | None
    released_at: str | None
    files: dict


class Project(NamedTuple):
    manifest: dict
    signature_json: str
    content_sha256: str
    release: dict | None = None


class Model:
    def __init__(self, directory, project, predict):
        self._directory = directory
        self._predict = predict
        self._signature = json.loads(project.signature_json)
        release = project.release or {}
        self._info = Info(
            project.manifest["name"],
            project.manifest["flavour"],
            project.content_sha256,
            project.manifest.get("model_id"),
            self._signature.get("signature_version"),
            release.get("version"),
            release.get("released_at"),
            dict(project.manifest.get("files", {})),
        )

    def info(self):
        return self._info

    def signature(self):
        return self._signature

    def predict(self, inputs):
        required = {entry["name"] for entry in self._signature["inputs"] if entry["parameters"]["required"]}
        if not required <= inputs.keys():
            raise ModelError("Signature", "inputs", f"missing required inputs [{sorted(required - inputs.keys())}]")
        slots = len(self._signature["parameters"].get("state", []))
        for entry in self._signature["inputs"]:
            if entry["shape"] == [-1] and entry["name"] in inputs and len(inputs[entry["name"]]) != slots:
                raise ModelError("Signature", "state", f"input [{entry['name']}] has [{len(inputs[entry['name']])}] values and the signature has [{slots}] slots")
        try:
            outputs = self._predict(inputs)
        except Exception as error:
            raise ModelError("Runtime", "predict", str(error)) from error
        integers = {entry["name"] for entry in self._signature["outputs"] if entry["datatype"] == "INT64"}
        return {name: [_integer(name, value) for value in values] if name in integers else values for name, values in outputs.items()}

    def verify(self):
        findings = replay(self._directory, self._signature, self.predict)
        if findings:
            raise ModelError("Verify", "replay", "; ".join(f"{rule} {message}" for rule, message in findings))


def load(directory):
    return build(directory, read_project(directory))


def read_project(directory):
    manifest_bytes = _read_bytes(join(directory, "project.json"))
    try:
        manifest = json.loads(manifest_bytes)
    except ValueError as error:
        raise ModelError("Load", "manifest", f"manifest unreadable [{error}]") from error
    for path, sha256 in manifest["files"].items():
        digest = hashlib.sha256()
        try:
            with open(join(directory, path), "rb") as file:
                for chunk in iter(lambda: file.read(1 << 20), b""):
                    digest.update(chunk)
        except OSError as error:
            raise ModelError("Load", "PJ003", f"file absent [{path}]") from error
        if digest.hexdigest() != sha256:
            raise ModelError("Load", "PJ003", f"file checksum mismatch [{path}]")
    if "evaluation.json" in manifest["files"]:
        if read_json(join(directory, "evaluation.json")).get("passed") is not True:
            raise ModelError("Load", "acceptance", "acceptance not passed")
    elif manifest["flavour"] != "static":
        raise ModelError("Load", "acceptance", f"no acceptance evaluation for flavour [{manifest['flavour']}]")
    signature_json = _read_bytes(join(directory, "signature.json")).decode()
    content_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    release = None
    if isfile(join(directory, "release.json")):
        release = read_json(join(directory, "release.json"))
        if not isinstance(release, dict) or release.get("content_sha256") != content_sha256 or not isinstance(release.get("version"), str) or not isinstance(release.get("released_at"), str):
            raise ModelError("Load", "release", f"release file differs from the project [{release.get('content_sha256') if isinstance(release, dict) else release}]")
    return Project(manifest, signature_json, content_sha256, release)


def build(directory, project):
    manifest = project.manifest
    flavour = manifest["flavour"]
    loaders = {"static": load_static, "wasm": load_wasm, "onnx": load_onnx, "pyfunc": load_pyfunc}
    if flavour not in loaders:
        raise ModelError("Load", "flavour", f"no loader for flavour [{flavour}]")
    source = json.dumps(manifest["constants"]) if flavour == "static" else join(directory, manifest["model"])
    try:
        predict = loaders[flavour](source, project.signature_json)
    except ImportError as error:
        raise ModelError("Load", "dependency", f"flavour [{flavour}] needs package [{error.name}]") from error
    except Exception as error:
        raise ModelError("Load", "driver", f"flavour [{flavour}] failed to load [{error}]") from error
    return Model(directory, project, predict)


def replay(directory, signature, predict):
    golden = read_json(join(directory, "golden.json"))
    tolerance = golden.get("tolerance", {})
    required = {entry["name"] for entry in signature["inputs"] if entry["parameters"]["required"]}
    findings = []
    for sequence in golden["sequences"]:
        for step in sequence["steps"]:
            step_id = step["request"]["id"]
            inputs = {entry["name"]: entry["data"] for entry in step["request"]["inputs"]}
            complete = required <= inputs.keys()
            if "error" in step:
                if complete:
                    findings.append(("RP001", f"step [{step_id}] expects a signature error but supplies every required input"))
                continue
            if not complete:
                findings.append(("RP002", f"step [{step_id}] is missing required inputs [{sorted(required - inputs.keys())}]"))
                continue
            try:
                outputs = predict(inputs)
            except Exception as error:
                findings.append(("RP005", f"step [{step_id}] the model gave no answer [{error}]"))
                continue
            findings.extend(
                ("RP003", f"step [{step_id}] output [{entry['name']}] is [{outputs.get(entry['name'])}] and the golden is [{entry['data']}]")
                for entry in step["response"]["outputs"]
                if not _within(outputs.get(entry["name"]), entry["data"], tolerance.get(entry["name"]))
            )
    return findings


def read_json(path):
    try:
        return json.loads(_read_bytes(path))
    except ValueError as error:
        raise ModelError("Load", "json", f"file unreadable [{path}] [{error}]") from error


def _read_bytes(path):
    try:
        with open(path, "rb") as file:
            return file.read()
    except OSError as error:
        raise ModelError("Load", "read", f"file unreadable [{path}] [{error}]") from error


def _integer(name, value):
    number = float(value)
    if not math.isfinite(number) or number != int(number) or abs(number) > 2**53:
        raise ModelError("Runtime", "datatype", f"INT64 output [{name}] is not an integer [{value}]")
    return int(number)


def _within(actual, expected, bounds):
    if actual is None or len(actual) != len(expected):
        return False
    if not bounds:
        return actual == expected
    absolute, relative = bounds.get("absolute", 0.0), bounds.get("relative", 0.0)
    return all(abs(value - truth) <= absolute + relative * abs(truth) for value, truth in zip(actual, expected, strict=True))


def load_static(constants_json, signature_json):
    constants = json.loads(constants_json)
    outputs = {name: [value] for name, value in constants.items()}
    return lambda _inputs: {name: list(values) for name, values in outputs.items()}


def load_wasm(path, signature_json):
    import struct

    import wasmtime

    fuel = 1_000_000
    memory_bytes = 1 << 20

    def math_function(name):
        function = getattr(math, name)

        def call(*values):
            try:
                return function(*values)
            except OverflowError:
                if name == "pow":
                    return -math.inf if values[0] < 0 and values[1] % 2 == 1 else math.inf
                return math.copysign(math.inf, values[0]) if name == "sinh" else math.inf
            except ValueError:
                if name in ("log", "log2", "log10") and values[0] == 0.0:
                    return -math.inf
                if name == "pow" and values[0] == 0.0 and values[1] < 0:
                    return -math.inf if math.copysign(1.0, values[0]) < 0 and values[1] % 2 == 1 else math.inf
                return math.nan

        return call

    signature = json.loads(signature_json)
    state_in = [entry for entry in signature["inputs"] if entry["shape"] == [-1]]
    state_slots = len(signature["parameters"].get("state", []))
    scalars_in = [entry for entry in signature["inputs"] if entry["shape"] != [-1]]
    outputs = signature["outputs"]
    config = wasmtime.Config()
    config.consume_fuel = True
    engine = wasmtime.Engine(config)
    module = wasmtime.Module.from_file(engine, path)
    linker = wasmtime.Linker(engine)
    arities = {"acos": 1, "asin": 1, "atan": 1, "atan2": 2, "cos": 1, "cosh": 1, "exp": 1, "log": 1, "log10": 1, "log2": 1, "pow": 2, "sin": 1, "sinh": 1, "tan": 1, "tanh": 1}
    for name, arity in arities.items():
        linker.define_func("asystem_math", name, wasmtime.FuncType([wasmtime.ValType.f64()] * arity, [wasmtime.ValType.f64()]), math_function(name))

    def predict(inputs):
        store = wasmtime.Store(engine)
        store.set_fuel(fuel)
        store.set_limits(memory_size=memory_bytes)
        instance = linker.instantiate(store, module)
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
            result[entry["name"]] = list(values[position : position + count])
            position += count
        return result

    return predict


def load_onnx(path, signature_json):
    import numpy
    import onnxruntime

    signature = json.loads(signature_json)
    session = onnxruntime.InferenceSession(path, providers=["CPUExecutionProvider"])
    outputs = signature["outputs"]

    def predict(inputs):
        feeds = {entry["name"]: numpy.array([inputs[entry["name"]]], dtype=numpy.float64) for entry in signature["inputs"] if entry["name"] in inputs}
        values = session.run([entry["name"] for entry in outputs], feeds)
        return {entry["name"]: [float(item) for item in numpy.asarray(value).flatten()] for entry, value in zip(outputs, values, strict=True)}

    return predict


def load_pyfunc(path, signature_json):
    import importlib.util
    import warnings

    import pandas
    from mlflow.models import model as mlflow_model

    spec = importlib.util.spec_from_file_location("project_model", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        spec.loader.exec_module(module)
    for warning in caught:
        if "type hint" not in str(warning.message):
            warnings.warn_explicit(warning.message, warning.category, warning.filename, warning.lineno)
    instance = getattr(mlflow_model, "__mlflow_model__")  # noqa: B009
    outputs = json.loads(signature_json)["outputs"]

    def predict(inputs):
        result = instance.predict(None, pandas.DataFrame(dict(inputs)))
        return {entry["name"]: [float(item) for item in result[entry["name"]]] for entry in outputs}

    return predict
