import json
from os.path import join

from consumer import run_onnx, run_pyfunc, run_static, run_wasm
from workbench.errors import GateError
from workbench.model import PROJECT_GOLDEN, PROJECT_SIGNATURE, verify_project


def replay_project(project_dir):
    manifest = verify_project(project_dir)
    with open(join(project_dir, PROJECT_SIGNATURE)) as signature_file:
        signature = json.load(signature_file)
    with open(join(project_dir, PROJECT_GOLDEN)) as golden_file:
        golden = json.load(golden_file)
    predict = _loader(project_dir, manifest, signature)
    tolerance = golden.get("tolerance", {})
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
                if not _within(actual, entry["data"], tolerance.get(entry["name"])):
                    findings.append(("RP003", f"step [{step_id}] output [{entry['name']}] is [{actual}] and the golden is [{entry['data']}]"))
    return findings


def _within(actual, expected, bounds):
    if actual is None or len(actual) != len(expected):
        return False
    if not bounds:
        return actual == expected
    absolute, relative = bounds.get("absolute", 0.0), bounds.get("relative", 0.0)
    return all(abs(value - truth) <= absolute + relative * abs(truth) for value, truth in zip(actual, expected, strict=True))


def require_replay(project_dir):
    findings = replay_project(project_dir)
    if findings:
        raise GateError("Package", "replay", "; ".join(f"{rule} {message}" for rule, message in findings))


def model_predict(model_path, flavour, signature):
    loaders = {"wasm": run_wasm.load_wasm, "onnx": run_onnx.load_onnx, "pyfunc": run_pyfunc.load_pyfunc}
    return loaders[flavour](model_path, json.dumps(signature))


def _loader(project_dir, manifest, signature):
    if manifest["flavour"] == "static":
        return run_static.load_static(json.dumps(manifest["constants"]), json.dumps(signature))
    return model_predict(join(project_dir, manifest["files"]["model"]["path"]), manifest["flavour"], signature)
