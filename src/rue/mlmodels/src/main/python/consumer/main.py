import hashlib
import json
import sys
import time
from os.path import join

from . import run_onnx, run_pyfunc, run_served, run_static, run_wasm


def main(arguments=None):
    arguments = sys.argv[1:] if arguments is None else arguments
    if len(arguments) not in (1, 3):
        print("ERROR usage consumer <project dir> [<server> <name>]", file=sys.stderr)
        return 2
    try:
        findings = replay(arguments[0], arguments[1:] or None)
    except (OSError, ValueError) as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 1
    for finding in findings:
        print(f"ERROR {finding}", file=sys.stderr)
    return 1 if findings else 0


def load_project(directory):
    manifest = read_json(join(directory, "project.json"))
    for key, entry in manifest["files"].items():
        try:
            with open(join(directory, entry["path"]), "rb") as file:
                content = file.read()
        except OSError as error:
            raise ValueError(f"PJ003 file absent [{key}]") from error
        if hashlib.sha256(content).hexdigest() != entry["sha256"]:
            raise ValueError(f"PJ003 file checksum mismatch [{key}]")
    if "evaluation" in manifest["files"]:
        if read_json(join(directory, manifest["files"]["evaluation"]["path"])).get("passed") is not True:
            raise ValueError("acceptance not passed")
    elif manifest["flavour"] != "static":
        raise ValueError(f"no acceptance evaluation for flavour [{manifest['flavour']}]")
    with open(join(directory, manifest["files"]["signature"]["path"])) as signature_file:
        signature_json = signature_file.read()
    return manifest, signature_json


def replay(directory, served):
    started = time.monotonic()
    manifest, signature_json = load_project(directory)
    report("verify", f"{len(manifest['files']) + 1} files", started)
    signature = json.loads(signature_json)
    url = None if served is None else f"{served[0]}/v2/models/{served[1]}/infer"
    started = time.monotonic()
    predict = new_predictor(directory, manifest, signature_json) if url is None else run_served.load_served(url, signature_json)
    report("load", manifest["flavour"] if url is None else "served", started)
    golden = read_json(join(directory, manifest["files"]["golden"]["path"]))
    started = time.monotonic()
    steps = 0
    required = {entry["name"] for entry in signature["inputs"] if entry["parameters"]["required"]}
    findings = []
    for sequence in golden["sequences"]:
        for step in sequence["steps"]:
            steps += 1
            step_id = step["request"]["id"]
            inputs = {entry["name"]: entry["data"] for entry in step["request"]["inputs"]}
            complete = required <= inputs.keys()
            if "error" in step:
                if complete:
                    findings.append(f"RP001 step [{step_id}] expects a signature error but supplies every required input")
                continue
            if not complete:
                findings.append(f"RP002 step [{step_id}] is missing required inputs")
                continue
            try:
                outputs = predict(inputs)
            except Exception as error:
                findings.append(f"RP005 step [{step_id}] the model gave no answer [{error}]")
                continue
            findings.extend(
                f"RP003 step [{step_id}] output [{entry['name']}] is [{outputs.get(entry['name'])}] and the golden is [{entry['data']}]"
                for entry in step["response"]["outputs"]
                if not within(outputs.get(entry["name"]), entry["data"], golden.get("tolerance", {}), entry["name"])
            )
    report("replay", f"{steps} steps", started)
    return findings


def new_predictor(directory, manifest, signature_json):
    flavour = manifest["flavour"]
    if flavour == "static":
        return run_static.load_static(json.dumps(manifest["constants"]), signature_json)
    loaders = {"wasm": run_wasm.load_wasm, "onnx": run_onnx.load_onnx, "pyfunc": run_pyfunc.load_pyfunc}
    if flavour not in loaders:
        raise ValueError(f"no consumer for flavour [{flavour}]")
    return loaders[flavour](join(directory, manifest["files"]["model"]["path"]), signature_json)


def within(actual, expected, tolerance, name):
    if actual is None or len(actual) != len(expected):
        return False
    if name not in tolerance:
        return actual == expected
    absolute, relative = tolerance[name].get("absolute", 0.0), tolerance[name].get("relative", 0.0)
    return all(abs(value - truth) <= absolute + relative * abs(truth) for value, truth in zip(actual, expected, strict=True))


def report(stage, detail, started):
    print(f"    {stage:<12} ... done [{detail}] ({time.monotonic() - started:.2f}s)", flush=True)


def read_json(path):
    try:
        with open(path) as file:
            return json.load(file)
    except OSError as error:
        raise ValueError(f"file unreadable [{path}] [{error}]") from error


if __name__ == "__main__":
    sys.exit(main())
