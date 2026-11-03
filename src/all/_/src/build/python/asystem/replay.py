import importlib.util
import json
import platform
import struct
from os.path import join

from asystem.model import PROJECT_GOLDEN, PROJECT_MANIFEST, PROJECT_SIGNATURE, file_sha256, verify_project

WASM_FUEL = 1_000_000
WASM_MEMORY_BYTES = 1 << 20
ARCHITECTURES = {"x86_64": "x86_64", "amd64": "x86_64", "aarch64": "aarch64", "arm64": "aarch64"}


def replay_project(project_dir):
    manifest = verify_project(project_dir)
    with open(join(project_dir, PROJECT_SIGNATURE)) as signature_file:
        signature = json.load(signature_file)
    with open(join(project_dir, PROJECT_GOLDEN)) as golden_file:
        golden = json.load(golden_file)
    predict = _loader(project_dir, manifest, signature)
    required = {entry["name"] for entry in signature["inputs"] if entry["parameters"]["required"]}
    findings = []
    for sequence in golden["sequences"]:
        for step in sequence["steps"]:
            step_id = step["request"]["id"]
            inputs = {entry["name"]: entry["data"] for entry in step["request"]["inputs"]}
            if "error" in step:
                if required <= inputs.keys():
                    findings.append(("RP001", f"step [{step_id}] expects a signature error but supplies every required input"))
                continue
            if not required <= inputs.keys():
                findings.append(("RP002", f"step [{step_id}] is missing required inputs {sorted(required - inputs.keys())}"))
                continue
            outputs = predict(inputs)
            for entry in step["response"]["outputs"]:
                actual = outputs.get(entry["name"])
                if actual != entry["data"]:
                    findings.append(("RP003", f"step [{step_id}] output [{entry['name']}] is [{actual}] and the golden is [{entry['data']}]"))
    return findings


def gate_project(project_dir, hosts=("python",)):
    findings = replay_project(project_dir)
    architecture = ARCHITECTURES[platform.machine().lower()]
    return {
        "project_sha256": file_sha256(join(project_dir, PROJECT_MANIFEST)),
        "results": [{"host": host, "arch": architecture, "passed": not findings} for host in hosts],
    }, findings


def model_predict(model_path, flavor, signature):
    if flavor == "wasm":
        return _wasm_predict(model_path, signature)
    if flavor == "onnx":
        return _onnx_predict(model_path, signature)
    return _pyfunc_predict(model_path, signature)


def _loader(project_dir, manifest, signature):
    if manifest["flavor"] == "static":
        constants = {name: [value] for name, value in manifest["constants"].items()}
        return lambda _inputs: dict(constants)
    return model_predict(join(project_dir, manifest["files"]["model"]["path"]), manifest["flavor"], signature)


def _wasm_predict(model_path, signature):
    import wasmtime

    state_in = [entry for entry in signature["inputs"] if entry["shape"] == [-1]]
    state_slots = len(signature["parameters"].get("state", []))
    scalars_in = [entry for entry in signature["inputs"] if entry["shape"] != [-1]]
    outputs = signature["outputs"]
    config = wasmtime.Config()
    config.consume_fuel = True
    engine = wasmtime.Engine(config)
    module = wasmtime.Module.from_file(engine, model_path)

    def predict(inputs):
        store = wasmtime.Store(engine)
        store.set_fuel(WASM_FUEL)
        store.set_limits(memory_size=WASM_MEMORY_BYTES)
        instance = wasmtime.Instance(store, module, [])
        memory = instance.exports(store)["memory"]
        function = instance.exports(store)["predict"]
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


def _onnx_predict(model_path, signature):
    import numpy
    import onnxruntime

    session = onnxruntime.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    outputs = signature["outputs"]

    def predict(inputs):
        feeds = {entry["name"]: numpy.array([inputs[entry["name"]]], dtype=numpy.float64) for entry in signature["inputs"] if entry["name"] in inputs}
        values = session.run([entry["name"] for entry in outputs], feeds)
        return {entry["name"]: [int(item) if entry["datatype"] == "INT64" else float(item) for item in numpy.asarray(value).flatten()] for entry, value in zip(outputs, values, strict=True)}

    return predict


def _pyfunc_predict(model_path, signature):
    import pandas
    from mlflow.models import model as mlflow_model

    spec = importlib.util.spec_from_file_location("project_model", model_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    instance = mlflow_model.__mlflow_model__
    outputs = signature["outputs"]

    def predict(inputs):
        frame = pandas.DataFrame(dict(inputs))
        result = instance.predict(None, frame)
        return {entry["name"]: [int(item) if entry["datatype"] == "INT64" else float(item) for item in result[entry["name"]]] for entry in outputs}

    return predict
