import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from os.path import isdir, isfile, join

PROJECT_SPEC_VERSION = 1
PROJECT_MANIFEST = "project.json"
PROJECT_SIGNATURE = "signature.json"
PROJECT_GOLDEN = "golden.json"
PROJECT_FLAVORS = ("static", "wasm", "onnx", "pyfunc")
PROJECT_MODEL_FILES = {"wasm": "model.wasm", "onnx": "model.onnx", "pyfunc": "model.py"}
PROJECT_SOURCES = ("static", "manual", "mlflow")
PROJECT_ALIAS_CANDIDATE = "candidate"
PROJECT_ALIAS_RELEASE = "release"
PROJECT_SPLITS = ("training", "validation", "backtest", "golden")
PROJECT_NAME = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
PROJECT_DATATYPES = ("FP64", "INT64")
PROJECT_UNIT_SUFFIXES = {"seconds": "_seconds", "percent": "_pct", "volts": "_volts", "hertz": "_hertz", "watt hours": "_wh", "celsius": "_celsius"}
PROJECT_REQUIRED_FILES = {"static": (), "wasm": ("model",), "onnx": ("model",), "pyfunc": ("model",)}
PROJECT_SIGNATURE_ERROR = "signature"


def registered_name(module, model, notebook):
    return "_".join(check_name(part) for part in (module, model, notebook))


def check_name(name):
    if not PROJECT_NAME.match(name):
        raise ValueError(f"name must be lowercase letters, digits and underscores in module and dimension style [{name}]")
    return name


def signature_input(name, unit, description, datatype="FP64", required=True, shape=None):
    return _signature_tensor(name, unit, description, datatype, required, shape)


def signature_output(name, unit, description, datatype="INT64", required=True, shape=None):
    return _signature_tensor(name, unit, description, datatype, required, shape)


def signature_state(name, unit, description):
    return {"name": name, "unit": unit, "description": description}


def build_signature(name, versions, inputs, outputs, state=(), signature_version=1):
    return {
        "name": name,
        "platform": "mlserver",
        "versions": list(versions),
        "parameters": {"signature_version": signature_version, "state": [{"slot": slot, **entry} for slot, entry in enumerate(state)]},
        "inputs": list(inputs),
        "outputs": list(outputs),
    }


def golden_step(signature, model_version, step_id, inputs, outputs=None, error=None):
    request = {"id": step_id, "inputs": [_tensor(signature["inputs"], name, value) for name, value in inputs.items()]}
    if error is not None:
        return {"request": request, "error": error}
    response = {
        "model_name": signature["name"],
        "model_version": model_version,
        "id": step_id,
        "outputs": [_tensor(signature["outputs"], name, value) for name, value in (outputs or {}).items()],
    }
    return {"request": request, "response": response}


def golden_document(model_version, sequences):
    return {"model_version": model_version, "sequences": [{"name": name, "steps": steps} for name, steps in sequences]}


def golden_from_samples(signature, model_version, samples, sequence="golden", constants=None):
    input_specs = {entry["name"]: entry for entry in signature["inputs"]}
    output_names = [entry["name"] for entry in signature["outputs"]]
    steps = []
    for index, sample in enumerate(samples):
        inputs = {name: _cell(spec, sample[name]) for name, spec in input_specs.items() if sample.get(name) is not None}
        step_id = f"s1-{index}"
        if sample.get("expect") == "error":
            steps.append(golden_step(signature, model_version, step_id, inputs, error=PROJECT_SIGNATURE_ERROR))
        else:
            outputs = dict(constants) if constants is not None else {name: sample[name] for name in output_names if sample.get(name) is not None}
            steps.append(golden_step(signature, model_version, step_id, inputs, outputs))
    return golden_document(model_version, [(sequence, steps)])


def package_project(project_dir, name, model_version, flavor, signature, samples, provenance, constants=None, model_path=None, sequence="golden"):
    golden = golden_from_samples(signature, model_version, samples, sequence, constants)
    return write_project(project_dir, name, model_version, flavor, signature, golden, provenance, constants, model_path)


def write_project(project_dir, name, model_version, flavor, signature, golden, provenance, constants=None, model_path=None, onnx=None):
    os.makedirs(project_dir, exist_ok=True)
    files = {"signature": PROJECT_SIGNATURE, "golden": PROJECT_GOLDEN}
    if model_path is not None:
        if flavor not in PROJECT_MODEL_FILES:
            raise ValueError(f"flavor [{flavor}] has no model file")
        shutil.copy(model_path, join(project_dir, PROJECT_MODEL_FILES[flavor]))
        files["model"] = PROJECT_MODEL_FILES[flavor]
    _write_json(join(project_dir, PROJECT_SIGNATURE), signature)
    _write_json(join(project_dir, PROJECT_GOLDEN), golden)
    manifest = {
        "spec_version": PROJECT_SPEC_VERSION,
        "name": name,
        "model_version": model_version,
        "signature_version": signature["parameters"]["signature_version"],
        "flavor": flavor,
        "provenance": provenance,
        "files": {key: {"path": file_name, "sha256": file_sha256(join(project_dir, file_name))} for key, file_name in files.items()},
    }
    if onnx is not None:
        manifest["onnx"] = onnx
    if constants is not None:
        manifest["constants"] = constants
    _write_json(join(project_dir, PROJECT_MANIFEST), manifest)
    return verify_project(project_dir)


def lint_project(project_dir):
    findings = []
    manifest_path = join(project_dir, PROJECT_MANIFEST)
    if not isfile(manifest_path):
        return [("PJ001", f"manifest missing [{manifest_path}]")]
    with open(manifest_path) as manifest_file:
        manifest = json.load(manifest_file)
    if manifest.get("spec_version") != PROJECT_SPEC_VERSION:
        findings.append(("PJ001", f"spec version unsupported [{manifest.get('spec_version')}]"))
    flavor = manifest.get("flavor")
    if flavor not in PROJECT_FLAVORS:
        findings.append(("PJ002", f"flavor unknown [{flavor}]"))
    provenance = manifest.get("provenance", {})
    if provenance.get("source") not in PROJECT_SOURCES:
        findings.append(("PJ002", f"provenance source unknown [{provenance.get('source')}]"))
    if not isinstance(provenance.get("inputs"), list):
        findings.append(("PJ002", "provenance inputs must be a list of the data files used"))
    if flavor in PROJECT_FLAVORS and flavor != "static" and not provenance.get("implementation"):
        findings.append(("PJ002", f"provenance implementation is needed for flavor [{flavor}]"))
    files = manifest.get("files", {})
    findings.extend(("PJ003", f"file missing from manifest [{key}]") for key in ("signature", "golden", *PROJECT_REQUIRED_FILES.get(flavor, ())) if key not in files)
    for key, entry in files.items():
        file_path = join(project_dir, entry["path"])
        if not isfile(file_path):
            findings.append(("PJ003", f"file absent [{key}] path [{entry['path']}]"))
        elif file_sha256(file_path) != entry["sha256"]:
            findings.append(("PJ003", f"file checksum mismatch [{key}] path [{entry['path']}]"))
    if "signature" not in files or not isfile(join(project_dir, files["signature"]["path"])):
        return findings
    with open(join(project_dir, files["signature"]["path"])) as signature_file:
        signature = json.load(signature_file)
    findings.extend(_lint_signature(manifest, signature))
    if "golden" in files and isfile(join(project_dir, files["golden"]["path"])):
        with open(join(project_dir, files["golden"]["path"])) as golden_file:
            golden = json.load(golden_file)
        findings.extend(_lint_golden(manifest, signature, golden))
    return findings


def verify_project(project_dir):
    findings = lint_project(project_dir)
    if findings:
        raise ValueError("; ".join(f"{rule} {message}" for rule, message in findings))
    with open(join(project_dir, PROJECT_MANIFEST)) as manifest_file:
        return json.load(manifest_file)


def register_project(project_dir, name, tracking_uri, aliases=(PROJECT_ALIAS_CANDIDATE,)):
    import mlflow
    from mlflow import MlflowClient

    manifest = verify_project(project_dir)
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(tracking_uri)
    mlflow.set_experiment(name)
    with mlflow.start_run() as run:
        mlflow.set_tags({"project_flavor": manifest["flavor"], "project_model_version": str(manifest["model_version"])})
        mlflow.log_artifacts(project_dir, artifact_path="project")
    version = mlflow.register_model(f"runs:/{run.info.run_id}/project", name)
    client = MlflowClient()
    for alias in aliases:
        client.set_registered_model_alias(name, alias, version.version)
    return version.version


def pull_model(name, alias, dest_dir, tracking_uri, signature_path=None):
    from mlflow.artifacts import download_artifacts
    from mlflow.exceptions import MlflowException

    import mlflow

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(tracking_uri)
    staging_dir = tempfile.mkdtemp(prefix=f"{name}-")
    try:
        try:
            download_artifacts(artifact_uri=f"models:/{name}@{alias}", dst_path=staging_dir)
        except MlflowException as error:
            if error.error_code == "RESOURCE_DOES_NOT_EXIST":
                return None
            raise
        project_dir = _find_project_dir(staging_dir)
        manifest = verify_project(project_dir)
        if signature_path is not None and isfile(signature_path):
            with open(signature_path) as expected_file, open(join(project_dir, PROJECT_SIGNATURE)) as pulled_file:
                differences = diff_signature(json.load(expected_file), json.load(pulled_file))
                if differences:
                    raise ValueError(f"pulled signature differs from [{signature_path}], a signature change is a release of the consumer: {'; '.join(differences)}")
        shutil.rmtree(dest_dir, ignore_errors=True)
        shutil.copytree(project_dir, dest_dir)
        return manifest
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def diff_signature(expected, actual):
    findings = []
    for section in ("inputs", "outputs"):
        expected_entries = {entry["name"]: entry for entry in expected[section]}
        actual_entries = {entry["name"]: entry for entry in actual[section]}
        singular = section[:-1]
        findings.extend(f"{singular} [{name}] is missing from the pulled signature" for name in sorted(expected_entries.keys() - actual_entries.keys()))
        findings.extend(f"{singular} [{name}] is new in the pulled signature" for name in sorted(actual_entries.keys() - expected_entries.keys()))
        findings.extend(
            f"{singular} [{name}] changed from {_brief(expected_entries[name])} to {_brief(actual_entries[name])}"
            for name in sorted(expected_entries.keys() & actual_entries.keys())
            if expected_entries[name] != actual_entries[name]
        )
    expected_state = [slot.get("name") for slot in expected["parameters"].get("state", [])]
    actual_state = [slot.get("name") for slot in actual["parameters"].get("state", [])]
    if expected_state != actual_state:
        findings.append(f"state slots changed from {expected_state} to {actual_state}")
    if expected["parameters"].get("signature_version") != actual["parameters"].get("signature_version"):
        findings.append(f"signature version changed from [{expected['parameters'].get('signature_version')}] to [{actual['parameters'].get('signature_version')}]")
    if not findings and _without_versions(expected) != _without_versions(actual):
        findings.append("signature differs in a field not listed above")
    return findings


def same_signature(expected, actual):
    return not diff_signature(expected, actual)


def render_rust(signature):
    required_inputs = [entry["name"] for entry in signature["inputs"] if entry["parameters"]["required"]]
    required_outputs = [entry["name"] for entry in signature["outputs"] if entry["parameters"]["required"]]
    lines = [
        "// WARNING: This file is written by the build process, any manual edits will be lost!",
        "use serde::{Deserialize, Serialize};",
        "",
        f'pub const NAME: &str = "{signature["name"]}";',
        f"pub const STATE_SLOTS: usize = {len(signature['parameters'].get('state', []))};",
        f"pub const INPUT_NAMES: &[&str] = &[{', '.join(_quoted(entry['name']) for entry in signature['inputs'])}];",
        f"pub const OUTPUT_NAMES: &[&str] = &[{', '.join(_quoted(entry['name']) for entry in signature['outputs'])}];",
        f"pub const REQUIRED_INPUT_NAMES: &[&str] = &[{', '.join(_quoted(name) for name in required_inputs)}];",
        f"pub const REQUIRED_OUTPUT_NAMES: &[&str] = &[{', '.join(_quoted(name) for name in required_outputs)}];",
    ]
    for struct, section in (("Request", "inputs"), ("Response", "outputs")):
        lines += ["", "#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]", f"pub struct {struct} {{"]
        for entry in signature[section]:
            rust_type = _rust_type(entry)
            if entry["parameters"]["required"]:
                lines.append(f"    pub {entry['name']}: {rust_type},")
            else:
                lines += ['    #[serde(default, skip_serializing_if = "Option::is_none")]', f"    pub {entry['name']}: Option<{rust_type}>,"]
        lines.append("}")
    return "\n".join(lines) + "\n"


def render_go(signature, package):
    required_inputs = [entry["name"] for entry in signature["inputs"] if entry["parameters"]["required"]]
    required_outputs = [entry["name"] for entry in signature["outputs"] if entry["parameters"]["required"]]
    lines = [
        "// WARNING: This file is written by the build process, any manual edits will be lost!",
        f"package {package}",
        "",
        f'const Name = "{signature["name"]}"',
        f"const StateSlots = {len(signature['parameters'].get('state', []))}",
        "",
        f"var InputNames = []string{{{', '.join(_quoted(entry['name']) for entry in signature['inputs'])}}}",
        f"var OutputNames = []string{{{', '.join(_quoted(entry['name']) for entry in signature['outputs'])}}}",
        f"var RequiredInputNames = []string{{{', '.join(_quoted(name) for name in required_inputs)}}}",
        f"var RequiredOutputNames = []string{{{', '.join(_quoted(name) for name in required_outputs)}}}",
    ]
    for struct, section in (("Request", "inputs"), ("Response", "outputs")):
        fields = []
        for entry in signature[section]:
            go_type = _go_type(entry)
            required = entry["parameters"]["required"]
            fields.append((_camel(entry["name"]), go_type if required or go_type.startswith("[]") else f"*{go_type}", f'`json:"{entry["name"]}{"" if required else ",omitempty"}"`'))
        name_width = max(len(name) for name, _, _ in fields)
        type_width = max(len(go_type) for _, go_type, _ in fields)
        lines += ["", f"type {struct} struct {{"]
        lines += [f"\t{name.ljust(name_width)} {go_type.ljust(type_width)} {tag}" for name, go_type, tag in fields]
        lines.append("}")
    return "\n".join(lines) + "\n"


def check_gate(gate, project_sha256, hosts, archs, reviewed_by):
    findings = []
    passed = {(result.get("host"), result.get("arch")) for result in gate.get("results", []) if result.get("passed") is True}
    findings.extend(("PM001", f"the parity gate has not passed for host [{host}] on [{arch}]") for host in hosts for arch in archs if (host, arch) not in passed)
    if gate.get("project_sha256") != project_sha256:
        findings.append(("PM002", f"the gate is for project [{gate.get('project_sha256')}] and the candidate is [{project_sha256}]"))
    if not reviewed_by:
        findings.append(("PM003", "a person must be named as the reviewer"))
    return findings


def promote_project(name, tracking_uri, gate_path, hosts, archs, reviewed_by):
    from mlflow import MlflowClient

    staging_dir = tempfile.mkdtemp(prefix=f"{name}-promote-")
    try:
        manifest = pull_model(name, PROJECT_ALIAS_CANDIDATE, join(staging_dir, "project"), tracking_uri)
        if manifest is None:
            raise ValueError(f"no registered model [{name}] with alias [{PROJECT_ALIAS_CANDIDATE}]")
        with open(gate_path) as gate_file:
            gate = json.load(gate_file)
        findings = check_gate(gate, file_sha256(join(staging_dir, "project", PROJECT_MANIFEST)), hosts, archs, reviewed_by)
        if findings:
            raise ValueError("; ".join(f"{rule} {message}" for rule, message in findings))
        client = MlflowClient()
        version = client.get_model_version_by_alias(name, PROJECT_ALIAS_CANDIDATE).version
        client.set_registered_model_alias(name, PROJECT_ALIAS_RELEASE, version)
        client.set_model_version_tag(name, version, "reviewed_by", reviewed_by)
        return version
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(arguments=None):
    parser = argparse.ArgumentParser(prog="asystem.model")
    commands = parser.add_subparsers(dest="command", required=True)
    pull = commands.add_parser("pull")
    pull.add_argument("name")
    pull.add_argument("alias")
    pull.add_argument("dest_dir")
    pull.add_argument("--signature")
    commands.add_parser("verify").add_argument("project_dir")
    commands.add_parser("lint").add_argument("project_dir")
    generate = commands.add_parser("generate")
    generate.add_argument("project_dir")
    generate.add_argument("--rust")
    generate.add_argument("--go")
    generate.add_argument("--go-package", default="model")
    promote = commands.add_parser("promote")
    promote.add_argument("name")
    promote.add_argument("--gate", required=True)
    promote.add_argument("--hosts", default="python,rust,go")
    promote.add_argument("--archs", default="x86_64,aarch64")
    promote.add_argument("--reviewed-by", required=True)
    options = parser.parse_args(arguments)
    try:
        if options.command == "pull":
            manifest = pull_model(options.name, options.alias, options.dest_dir, os.environ["MLFLOW_TRACKING_URI"], options.signature)
            if manifest is None:
                print(f"no registered model [{options.name}] alias [{options.alias}], nothing pulled")
            else:
                print(f"pulled model [{options.name}] alias [{options.alias}] version [{manifest['model_version']}]")
        elif options.command == "verify" and isdir(options.project_dir):
            manifest = verify_project(options.project_dir)
            print(f"verified model [{manifest['name']}] version [{manifest['model_version']}]")
        elif options.command == "lint":
            findings = lint_project(options.project_dir)
            for rule, message in findings:
                print(f"{options.project_dir}: {rule} {message}", file=sys.stderr)
            return 1 if findings else 0
        elif options.command == "generate":
            with open(join(options.project_dir, PROJECT_SIGNATURE)) as signature_file:
                signature = json.load(signature_file)
            if options.rust:
                _write_text(options.rust, render_rust(signature))
            if options.go:
                _write_text(options.go, render_go(signature, options.go_package))
        elif options.command == "promote":
            version = promote_project(options.name, os.environ["MLFLOW_TRACKING_URI"], options.gate, options.hosts.split(","), options.archs.split(","), options.reviewed_by)
            print(f"promoted model [{options.name}] version [{version}] to alias [{PROJECT_ALIAS_RELEASE}]")
    except (ValueError, KeyError, OSError) as error:
        print(f"ERROR model command failed [{options.command}] [{error}]", file=sys.stderr)
        return 1
    return 0


def _signature_tensor(name, unit, description, datatype, required, shape):
    return {"name": name, "datatype": datatype, "shape": list(shape) if shape is not None else [1], "parameters": {"unit": unit, "required": required, "description": description}}


def _write_text(path, text):
    with open(path, "w") as target:
        target.write(text)
    print(f"wrote [{path}]")


def _cell(spec, value):
    return [float(item) for item in value.split()] if spec["shape"] == [-1] and isinstance(value, str) else value


def _quoted(text):
    return f'"{text}"'


def _brief(entry):
    return f"{entry['datatype']} {entry['shape']} unit [{entry['parameters']['unit']}] required [{entry['parameters']['required']}]"


def _without_versions(signature):
    return {key: value for key, value in signature.items() if key != "versions"}


def _rust_type(entry):
    base = {"FP64": "f64", "INT64": "i64"}[entry["datatype"]]
    return f"Vec<{base}>" if entry["shape"] == [-1] else base


def _go_type(entry):
    base = {"FP64": "float64", "INT64": "int64"}[entry["datatype"]]
    return f"[]{base}" if entry["shape"] == [-1] else base


def _camel(name):
    return "".join(part.capitalize() for part in name.split("_"))


def _tensor(specs, name, value):
    spec = next((entry for entry in specs if entry["name"] == name), None)
    data = list(value) if isinstance(value, (list, tuple)) else [value]
    datatype = spec["datatype"] if spec is not None else "FP64"
    data = [float(item) if datatype == "FP64" else int(item) for item in data]
    return {"name": name, "datatype": datatype, "shape": [len(data)], "data": data}


def _lint_signature(manifest, signature):
    findings = []
    name = manifest.get("name", "")
    if not PROJECT_NAME.match(name):
        findings.append(("PJ004", f"name does not follow the naming style [{name}]"))
    if signature.get("name") != name:
        findings.append(("PJ004", f"signature name [{signature.get('name')}] differs from the project name [{name}]"))
    if signature["parameters"]["signature_version"] != manifest.get("signature_version"):
        findings.append(("PJ005", f"signature version mismatch manifest [{manifest.get('signature_version')}] signature [{signature['parameters']['signature_version']}]"))
    if str(manifest.get("model_version")) not in [str(version) for version in signature.get("versions", [])]:
        findings.append(("PJ005", f"model version [{manifest.get('model_version')}] is not in the signature versions {signature.get('versions')}"))
    names = [entry["name"] for entry in signature["inputs"] + signature["outputs"]]
    if len(set(names)) != len(names):
        findings.append(("PJ006", "input and output names must be unique"))
    for entry in signature["inputs"] + signature["outputs"]:
        parameters = entry.get("parameters", {})
        if entry.get("datatype") not in PROJECT_DATATYPES or not isinstance(entry.get("shape"), list):
            findings.append(("PJ006", f"datatype or shape invalid [{entry['name']}]"))
        if not PROJECT_NAME.match(entry["name"]):
            findings.append(("PJ006", f"name does not follow the naming style [{entry['name']}]"))
        if not parameters.get("unit") or not isinstance(parameters.get("required"), bool) or not parameters.get("description"):
            findings.append(("PJ006", f"unit, required and description are needed [{entry['name']}]"))
    slots = signature["parameters"].get("state", [])
    if [slot.get("slot") for slot in slots] != list(range(len(slots))):
        findings.append(("PJ006", "state slots must be numbered from 0 in order"))
    if len({slot.get("name") for slot in slots}) != len(slots):
        findings.append(("PJ006", "state slot names must be unique"))
    module = name.split("_")[0]
    for entry in signature["outputs"]:
        unit = entry.get("parameters", {}).get("unit")
        if not entry["name"].startswith(f"{module}_"):
            findings.append(("PJ007", f"output [{entry['name']}] must start with the module [{module}_]"))
        if unit in PROJECT_UNIT_SUFFIXES and not entry["name"].endswith(PROJECT_UNIT_SUFFIXES[unit]):
            findings.append(("PJ007", f"output [{entry['name']}] with unit [{unit}] must end with [{PROJECT_UNIT_SUFFIXES[unit]}]"))
    output_names = {entry["name"] for entry in signature["outputs"]}
    constants = manifest.get("constants", {})
    findings.extend(("PJ008", f"constant [{constant}] is not a signature output") for constant in constants if constant not in output_names)
    if manifest.get("flavor") == "static":
        required = {entry["name"] for entry in signature["outputs"] if entry["parameters"]["required"]}
        findings.extend(("PJ008", f"a static project must give a constant for the required output [{missing}]") for missing in sorted(required - set(constants)))
    return findings


def _lint_golden(manifest, signature, golden):
    findings = []
    if str(golden.get("model_version")) != str(manifest.get("model_version")):
        findings.append(("PJ009", f"golden model version [{golden.get('model_version')}] differs from the manifest [{manifest.get('model_version')}]"))
    input_specs = {entry["name"]: entry for entry in signature["inputs"]}
    output_specs = {entry["name"]: entry for entry in signature["outputs"]}
    required_inputs = {name for name, entry in input_specs.items() if entry["parameters"]["required"]}
    required_outputs = {name for name, entry in output_specs.items() if entry["parameters"]["required"]}
    state_inputs = {name for name, entry in input_specs.items() if entry["shape"] == [-1]}
    constants = manifest.get("constants", {})
    sequences = golden.get("sequences", [])
    if not sequences:
        findings.append(("PJ010", "golden needs at least one sequence"))
    steps_seen = []
    for sequence in sequences:
        ids = [step.get("request", {}).get("id") for step in sequence.get("steps", [])]
        if len(set(ids)) != len(ids):
            findings.append(("PJ010", f"step ids must be unique in sequence [{sequence.get('name')}]"))
        steps_seen.extend(sequence.get("steps", []))
    has_error = False
    has_stateless_ok = False
    for step in steps_seen:
        request = step.get("request", {})
        given = {entry["name"] for entry in request.get("inputs", [])}
        if ("response" in step) == ("error" in step):
            findings.append(("PJ010", f"step [{request.get('id')}] must have exactly one of response and error"))
            continue
        findings.extend(("PJ010", f"step [{request.get('id')}] names an input that is not in the signature [{name}]") for name in sorted(given - set(input_specs)))
        if "error" in step:
            has_error = True
            if step["error"] != PROJECT_SIGNATURE_ERROR:
                findings.append(("PJ010", f"step [{request.get('id')}] error must be [{PROJECT_SIGNATURE_ERROR}]"))
            if not required_inputs - given:
                findings.append(("PJ010", f"step [{request.get('id')}] expects a signature error but supplies every required input"))
            continue
        if required_inputs - given:
            findings.append(("PJ010", f"step [{request.get('id')}] is missing required inputs {sorted(required_inputs - given)}"))
        if not given & state_inputs:
            has_stateless_ok = True
        outputs = {entry["name"]: entry["data"] for entry in step["response"].get("outputs", [])}
        findings.extend(("PJ010", f"step [{request.get('id')}] names an output that is not in the signature [{name}]") for name in sorted(set(outputs) - set(output_specs)))
        if required_outputs - set(outputs):
            findings.append(("PJ010", f"step [{request.get('id')}] is missing required outputs {sorted(required_outputs - set(outputs))}"))
        if manifest.get("flavor") == "static":
            for name, constant in constants.items():
                if outputs.get(name) != [constant]:
                    findings.append(("PJ012", f"step [{request.get('id')}] output [{name}] must equal the constant [{constant}]"))
    if not has_error:
        findings.append(("PJ011", "golden needs a step that expects a signature error, a request with a required input missing"))
    if signature["parameters"].get("state") and not has_stateless_ok:
        findings.append(("PJ011", "golden needs a first call with no state"))
    return findings


def _find_project_dir(root_dir):
    for current_dir, _, file_names in os.walk(root_dir):
        if PROJECT_MANIFEST in file_names:
            return current_dir
    raise ValueError(f"no project found under [{root_dir}]")


def _write_json(path, document):
    with open(path, "w") as file:
        json.dump(document, file, indent=2, sort_keys=False)
        file.write("\n")


if __name__ == "__main__":
    sys.exit(main())
