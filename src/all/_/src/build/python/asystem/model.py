import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from os.path import basename, dirname, isfile, join, relpath

from asystem.errors import GateError
from asystem.metadata import content_sha256

PROJECT_SPEC_VERSION = 1
CONSUMER_MODEL_PATH = "src/build/resources/model"
PROJECT_MANIFEST = "project.json"
PROJECT_SIGNATURE = "signature.json"
PROJECT_GOLDEN = "golden.json"
PROJECT_EVALUATION = "evaluation.json"
ACCEPTANCE_SPLITS = ("validation", "backtest")
ACCEPTANCE_DIRECTIONS = ("max", "min")
PROJECT_FLAVOURS = ("static", "wasm", "onnx", "pyfunc")
PROJECT_PLACEHOLDERS = ("tbd", "todo", "unknown", "none", "n/a", "not applicable", "to be determined")
PROJECT_MODEL_FILES = {"wasm": "model.wasm", "onnx": "model.onnx", "pyfunc": "model.py"}
PROJECT_SOURCES = ("static", "manual", "mlflow")
WASM_MATH_MODULE = "asystem_math"
WASM_MATH_FUNCTIONS = {"acos": 1, "asin": 1, "atan": 1, "atan2": 2, "cos": 1, "cosh": 1, "exp": 1, "log": 1, "log10": 1, "log2": 1, "pow": 2, "sin": 1, "sinh": 1, "tan": 1, "tanh": 1}
PYFUNC_BASE_IMPORTS = ("mlflow", "numpy", "pandas")
PYFUNC_IMPORT_NAMES = {"scikit_learn": "sklearn", "python_dateutil": "dateutil", "pyyaml": "yaml", "pillow": "PIL"}
PROJECT_ALIAS_PREVIEW = "preview"
PROJECT_ALIAS_RELEASE = "release"
PROJECT_SPLITS = ("training", "validation", "backtest", "golden")
PROJECT_NAME = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
PROJECT_DATATYPES = ("FP64", "INT64")
PROJECT_UNIT_SUFFIXES = {"seconds": "_seconds", "percent": "_pct", "volts": "_volts", "hertz": "_hertz", "watt hours": "_wh", "celsius": "_celsius"}
PROJECT_REQUIRED_FILES = {"static": (), "wasm": ("model",), "onnx": ("model",), "pyfunc": ("model",)}
PROJECT_SIGNATURE_ERROR = "signature"
PROJECT_FIX_HINTS = {
    "PJ": "rerun the notebook, since the committed or pulled project is not the one its manifest describes",
    "NB": "fix the notebook structure, then run fab unittest in datascience to restyle it",
    "WS": "fix the workspace layout under src/main/notebook",
    "AC": "fix the acceptance check or its data in the notebook and rerun it",
    "CP": "run fab generate in the consumer, which embeds the released project again",
    "RP": "the model no longer returns its golden file, fix the model or regenerate the golden file in the notebook",
    "PM004": "fix the acceptance failure and rerun the notebook",
    "MD": "rerun fab unittest in datascience, which writes the project and its metadata together",
}


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


def build_signature(name, inputs, outputs, state=(), signature_version=1):
    return {
        "name": name,
        "platform": "mlserver",
        "parameters": {"signature_version": signature_version, "state": [{"slot": slot, **entry} for slot, entry in enumerate(state)]},
        "inputs": list(inputs),
        "outputs": list(outputs),
    }


def golden_step(signature, step_id, inputs, outputs=None, error=None):
    request = {"id": step_id, "inputs": [_tensor(signature["inputs"], name, value) for name, value in inputs.items()]}
    if error is not None:
        return {"request": request, "error": error}
    response = {
        "model_name": signature["name"],
        "id": step_id,
        "outputs": [_tensor(signature["outputs"], name, value) for name, value in (outputs or {}).items()],
    }
    return {"request": request, "response": response}


def golden_document(sequences, tolerance=None):
    document = {"sequences": [{"name": name, "steps": steps} for name, steps in sequences]}
    if tolerance:
        document["tolerance"] = tolerance
    return document


def golden_from_samples(signature, samples, sequence="golden", constants=None, tolerance=None):
    input_specs = {entry["name"]: entry for entry in signature["inputs"]}
    output_specs = {entry["name"]: entry for entry in signature["outputs"]}
    output_names = list(output_specs)
    steps = []
    for index, sample in enumerate(samples):
        inputs = {name: _cell(spec, sample[name]) for name, spec in input_specs.items() if sample.get(name) is not None}
        step_id = f"s1-{index}"
        if sample.get("expect") == "error":
            steps.append(golden_step(signature, step_id, inputs, error=PROJECT_SIGNATURE_ERROR))
        else:
            outputs = dict(constants) if constants is not None else {name: _cell(output_specs[name], sample[name]) for name in output_names if sample.get(name) is not None}
            steps.append(golden_step(signature, step_id, inputs, outputs))
    return golden_document([(sequence, steps)], tolerance)


def measure(y_true, y_pred):
    import numpy

    truth = numpy.asarray(y_true, dtype=float)
    predicted = numpy.asarray(y_pred, dtype=float)
    if truth.size == 0 or truth.shape != predicted.shape:
        raise ValueError(f"measure needs equal non-empty samples [{truth.shape}] [{predicted.shape}]")
    error = predicted - truth
    spread = float(numpy.sum((truth - truth.mean()) ** 2))
    constant = truth.size < 2 or float(truth.std()) == 0.0 or float(predicted.std()) == 0.0
    return {
        "rmse": float(numpy.sqrt(numpy.mean(error**2))),
        "mae": float(numpy.mean(numpy.abs(error))),
        "max_abs_error": float(numpy.max(numpy.abs(error))),
        "bias": float(numpy.mean(error)),
        "p95_abs_error": float(numpy.percentile(numpy.abs(error), 95)),
        "r2": None if spread == 0.0 else float(1.0 - numpy.sum(error**2) / spread),
        "pearson_r": None if constant else float(numpy.corrcoef(truth, predicted)[0, 1]),
    }


def evaluate_acceptance(check, datasets):
    entries = check()
    if not isinstance(entries, list) or not entries:
        raise ValueError("the acceptance check must return a non-empty list of checks")
    checks = []
    for entry in entries:
        direction, limit, value = entry.get("direction"), entry.get("limit"), entry.get("value")
        if direction not in ACCEPTANCE_DIRECTIONS or isinstance(limit, bool) or not isinstance(limit, (int, float)) or (direction == "min" and limit <= 0) or limit < 0:
            raise ValueError(f"an acceptance check needs a direction of {list(ACCEPTANCE_DIRECTIONS)} and a limit that is positive for min [{entry.get('name')}]")
        passed, budget = _acceptance_outcome(value, limit, direction)
        checks.append({**entry, "gate": entry.get("gate", True), "passed": passed, "budget": budget})
    evaluation = {
        "datasets": {split: [{"path": f"{basename(dirname(path))}/{basename(path)}", "sha256": file_sha256(path)} for path in sorted(paths)] for split, paths in datasets.items()},
        "checks": checks,
        "passed": all(entry["passed"] for entry in checks if entry["gate"]),
        "budget": _acceptance_budget(checks),
    }
    print(f"acceptance [{'passed' if evaluation['passed'] else 'failed'}] budget [{evaluation['budget']}]")
    return evaluation


def check_acceptance(project_dir):
    evaluation_path = join(project_dir, PROJECT_EVALUATION)
    if not isfile(evaluation_path):
        return [("PM004", "the project has no acceptance evaluation")]
    with open(evaluation_path) as evaluation_file:
        evaluation = json.load(evaluation_file)
    return [
        ("PM004", f"acceptance failed split [{entry['split']}] output [{entry['output']}] check [{entry['name']}] value [{entry['value']}]")
        for entry in evaluation["checks"]
        if entry["gate"] and not entry["passed"]
    ]


def package_project(project_dir, name, flavour, signature, samples, provenance, constants=None, model_path=None, sequence="golden", evaluation=None, tolerance=None, python_deps=None):
    golden = golden_from_samples(signature, samples, sequence, constants, tolerance)
    return write_project(project_dir, name, flavour, signature, golden, provenance, constants, model_path, evaluation=evaluation, python_deps=python_deps)


def write_project(project_dir, name, flavour, signature, golden, provenance, constants=None, model_path=None, onnx=None, evaluation=None, python_deps=None):
    os.makedirs(project_dir, exist_ok=True)
    files = {"signature": PROJECT_SIGNATURE, "golden": PROJECT_GOLDEN}
    if evaluation is not None:
        _write_json(join(project_dir, PROJECT_EVALUATION), evaluation)
        files["evaluation"] = PROJECT_EVALUATION
    if model_path is not None:
        if flavour not in PROJECT_MODEL_FILES:
            raise ValueError(f"flavour [{flavour}] has no model file")
        shutil.copy(model_path, join(project_dir, PROJECT_MODEL_FILES[flavour]))
        files["model"] = PROJECT_MODEL_FILES[flavour]
    _write_json(join(project_dir, PROJECT_SIGNATURE), signature)
    _write_json(join(project_dir, PROJECT_GOLDEN), golden)
    manifest = {
        "spec_version": PROJECT_SPEC_VERSION,
        "name": name,
        "signature_version": signature["parameters"]["signature_version"],
        "flavour": flavour,
        "provenance": provenance,
        "files": {key: {"path": file_name, "sha256": file_sha256(join(project_dir, file_name))} for key, file_name in files.items()},
    }
    if onnx is not None:
        manifest["onnx"] = onnx
    if flavour == "pyfunc":
        manifest["runtime"] = {"python": sorted(set(python_deps or ()))}
    elif python_deps:
        raise ValueError(f"flavour [{flavour}] takes no python dependencies")
    if flavour == "wasm" and model_path is not None:
        manifest["runtime"] = {"wasm": sorted({str(entry.name) for entry in _wasm_module_imports(model_path)})}
    if constants is not None:
        manifest["constants"] = constants
    _write_json(join(project_dir, PROJECT_MANIFEST), manifest)
    verified = verify_project(project_dir)
    if evaluation is not None and not evaluation["passed"]:
        raise GateError("Evaluate", "acceptance", "; ".join(f"{rule} {message}" for rule, message in check_acceptance(project_dir)))
    return verified


def lint_project(project_dir):
    findings = []
    manifest_path = join(project_dir, PROJECT_MANIFEST)
    if not isfile(manifest_path):
        return [("PJ001", f"manifest missing [{manifest_path}]")]
    with open(manifest_path) as manifest_file:
        manifest = json.load(manifest_file)
    if manifest.get("spec_version") != PROJECT_SPEC_VERSION:
        findings.append(("PJ001", f"spec version unsupported [{manifest.get('spec_version')}]"))
    flavour = manifest.get("flavour")
    if flavour not in PROJECT_FLAVOURS:
        findings.append(("PJ002", f"flavour unknown [{flavour}]"))
    provenance = manifest.get("provenance", {})
    if provenance.get("source") not in PROJECT_SOURCES:
        findings.append(("PJ002", f"provenance source unknown [{provenance.get('source')}]"))
    if not isinstance(provenance.get("inputs"), list):
        findings.append(("PJ002", "provenance inputs must be a list of the data files used"))
    if flavour in PROJECT_FLAVOURS and flavour != "static":
        implementation = provenance.get("implementation")
        if not isinstance(implementation, str) or len(implementation.split()) < 2 or implementation.strip().lower() in PROJECT_PLACEHOLDERS:
            findings.append(("PJ002", f"provenance implementation must say what is inside the model for flavour [{flavour}]"))
    files = manifest.get("files", {})
    findings.extend(("PJ003", f"file missing from manifest [{key}]") for key in ("signature", "golden", *PROJECT_REQUIRED_FILES.get(flavour, ())) if key not in files)
    for key, entry in files.items():
        file_path = join(project_dir, entry["path"])
        if not isfile(file_path):
            findings.append(("PJ003", f"file absent [{key}] path [{entry['path']}]"))
        elif file_sha256(file_path) != entry["sha256"]:
            findings.append(("PJ003", f"file checksum mismatch [{key}] path [{entry['path']}]"))
    if flavour == "wasm" and "model" in files and isfile(join(project_dir, files["model"]["path"])):
        import wasmtime

        f64 = wasmtime.ValType.f64()
        for entry in _wasm_module_imports(join(project_dir, files["model"]["path"])):
            kind = entry.type
            if (
                entry.module != WASM_MATH_MODULE
                or entry.name not in WASM_MATH_FUNCTIONS
                or not isinstance(kind, wasmtime.FuncType)
                or list(kind.params) != [f64] * WASM_MATH_FUNCTIONS[entry.name]
                or list(kind.results) != [f64]
            ):
                findings.append(("PJ016", f"wasm module imports something other than a maths function [{entry.module}] [{entry.name}]"))
    runtime = manifest.get("runtime")
    if flavour == "pyfunc" or (flavour == "wasm" and "model" in files):
        kind = "python" if flavour == "pyfunc" else "wasm"
        listed = runtime.get(kind) if isinstance(runtime, dict) else None
        if not isinstance(listed, list) or not all(isinstance(name, str) for name in listed) or listed != sorted(set(listed)):
            findings.append(("PJ017", f"runtime [{kind}] must be a sorted list of unique names for flavour [{flavour}]"))
        else:
            findings.extend(("PJ017", f"runtime holds a key the flavour does not use [{key}]") for key in sorted(set(runtime) - {kind}))
            model_file = join(project_dir, files["model"]["path"]) if "model" in files else None
            if model_file is not None and isfile(model_file) and flavour == "wasm":
                actual = sorted({str(entry.name) for entry in _wasm_module_imports(model_file)})
                if listed != actual:
                    findings.append(("PJ017", f"runtime wasm differs from the module imports runtime {listed} module {actual}"))
            elif model_file is not None and isfile(model_file):
                with open(model_file) as source_file:
                    tree = ast.parse(source_file.read())
                imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
                imported |= {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module}
                needed = imported - set(sys.stdlib_module_names) - set(PYFUNC_BASE_IMPORTS)
                declared = {PYFUNC_IMPORT_NAMES.get(re.sub(r"[-_.]+", "_", name.lower()), re.sub(r"[-_.]+", "_", name.lower())): name for name in listed}
                findings.extend(("PJ017", f"model imports a package that runtime python does not declare [{name}]") for name in sorted(needed - set(declared)))
                findings.extend(("PJ017", f"runtime python declares a package the model does not need [{declared[name]}]") for name in sorted(set(declared) - needed))
    elif runtime is not None:
        findings.append(("PJ017", f"flavour [{flavour}] takes no runtime"))
    if "signature" not in files or not isfile(join(project_dir, files["signature"]["path"])):
        return findings
    with open(join(project_dir, files["signature"]["path"])) as signature_file:
        signature = json.load(signature_file)
    findings.extend(_lint_signature(manifest, signature))
    if "evaluation" in files:
        findings.extend(_lint_evaluation(project_dir, files, signature))
    elif flavour in PROJECT_FLAVOURS and flavour != "static":
        findings.append(("AC001", f"a project of flavour [{flavour}] needs an acceptance evaluation"))
    if "golden" in files and isfile(join(project_dir, files["golden"]["path"])):
        with open(join(project_dir, files["golden"]["path"])) as golden_file:
            golden = json.load(golden_file)
        findings.extend(_lint_golden(manifest, signature, golden))
    return findings


def verify_project(project_dir):
    findings = lint_project(project_dir)
    if findings:
        raise GateError("Package", "project", "; ".join(f"{rule} {message}" for rule, message in findings))
    with open(join(project_dir, PROJECT_MANIFEST)) as manifest_file:
        return json.load(manifest_file)


def register_project(project_dir, name, tracking_uri, aliases=(PROJECT_ALIAS_PREVIEW,), snapshot_version=None):
    import mlflow.pyfunc

    import mlflow

    manifest = verify_project(project_dir)
    client = registry_client(tracking_uri)
    content = content_sha256(project_dir)
    version = next((candidate for candidate in client.search_model_versions(f"name = '{name}'") if candidate.tags.get("content_sha256") == content), None)
    if version is None:
        if tracking_uri.startswith("sqlite:///") and client.get_experiment_by_name(name) is None:
            client.create_experiment(name, artifact_location="file://" + join(dirname(os.path.abspath(tracking_uri.removeprefix("sqlite:///"))), "artifacts"))
        mlflow.set_experiment(name)
        with mlflow.start_run(tags={"mlflow.source.name": "datascience"}) as run:
            mlflow.set_tags({"project_flavour": manifest["flavour"]})
            if "evaluation" in manifest["files"]:
                import pandas
                from mlflow.data.pandas_dataset import from_pandas

                with open(join(project_dir, PROJECT_EVALUATION)) as evaluation_file:
                    evaluation = json.load(evaluation_file)
                mlflow.set_tags({"acceptance": "passed" if evaluation["passed"] else "failed", "acceptance_budget": str(evaluation["budget"])})
                mlflow.log_metrics({"acceptance_passed": float(evaluation["passed"]), **({"acceptance_budget": evaluation["budget"]} if evaluation["budget"] is not None else {})})
                mlflow.log_metrics({f"{entry['split']}/{entry['output']}/{entry['name']}": entry["value"] for entry in evaluation["checks"] if entry["value"] is not None})
                for split, entries in evaluation["datasets"].items():
                    for entry in entries:
                        dataset = from_pandas(pandas.DataFrame(), name=os.path.splitext(basename(entry["path"]))[0], digest=entry["sha256"][:16])
                        mlflow.log_input(dataset, context=split)
            if manifest["flavour"] == "pyfunc":
                import pandas
                from mlflow.models import ModelSignature
                from mlflow.types import ColSpec, Schema

                with open(join(project_dir, manifest["files"]["signature"]["path"])) as signature_file:
                    signature = json.load(signature_file)
                column_types = {"FP64": "double", "INT64": "long"}
                with open(join(project_dir, manifest["files"]["golden"]["path"])) as golden_file:
                    golden = json.load(golden_file)
                first_step = next(step for sequence in golden["sequences"] for step in sequence["steps"] if "error" not in step)

                def schema(entries):
                    for entry in entries:
                        if entry["datatype"] not in column_types or entry["shape"] != [1]:
                            raise ValueError(f"pyfunc signature supports scalar FP64 and INT64 only [{entry['name']}]")
                    return Schema([ColSpec(column_types[entry["datatype"]], entry["name"]) for entry in entries])

                mlflow.pyfunc.log_model(
                    name="project",
                    python_model=join(project_dir, manifest["files"]["model"]["path"]),
                    artifacts={"project": project_dir},
                    signature=ModelSignature(inputs=schema(signature["inputs"]), outputs=schema(signature["outputs"])),
                    input_example=pandas.DataFrame({entry["name"]: entry["data"] for entry in first_step["request"]["inputs"]}),
                )
            else:
                mlflow.log_artifacts(project_dir, artifact_path="project")
        if manifest["flavour"] == "pyfunc":
            version = mlflow.register_model(f"runs:/{run.info.run_id}/project", name)
        else:
            if not client.search_registered_models(filter_string=f"name = '{name}'"):
                client.create_registered_model(name)
            version = client.create_model_version(name, f"{run.info.artifact_uri}/project", run_id=run.info.run_id)
        for key, value in {"content_sha256": content, "project_flavour": manifest["flavour"]}.items():
            client.set_model_version_tag(name, version.version, key, value)
    if snapshot_version is not None and "snapshot_version" not in version.tags and "release_version" not in version.tags:
        client.set_model_version_tag(name, version.version, "snapshot_version", snapshot_version)
    for alias in aliases:
        client.set_registered_model_alias(name, alias, version.version)
    return version.version


def register_preview(project_dir, name, tracking_uri, targets, snapshot_version=None):
    if not any(target["kind"] == "served" for target in targets):
        return None
    return register_project(project_dir, name, tracking_uri, aliases=(PROJECT_ALIAS_PREVIEW,), snapshot_version=snapshot_version)


def registry_client(tracking_uri):
    import mlflow
    from mlflow import MlflowClient

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(tracking_uri)
    return MlflowClient()


def registry_address(uri):
    from urllib.parse import urlparse

    if not uri:
        raise ValueError("MLFLOW_TRACKING_URI is not set")
    if urlparse(uri).port is not None:
        raise ValueError(f"registry address [{uri}] names a published port, use the proxy name, since the published port refuses every call but /health with an invalid host header")
    return uri


def check_release(project_dir):
    verify_project(project_dir)
    return check_acceptance(project_dir)


def pull_model(name, alias, dest_dir, tracking_uri):
    from mlflow.artifacts import download_artifacts
    from mlflow.exceptions import MlflowException

    client = registry_client(tracking_uri)
    staging_dir = tempfile.mkdtemp(prefix=f"{name}-")
    try:
        try:
            tags = client.get_model_version_by_alias(name, alias).tags
            download_artifacts(artifact_uri=f"models:/{name}@{alias}", dst_path=staging_dir)
        except MlflowException as error:
            if _not_found(error):
                return None
            raise
        project_dir = _find_project_dir(staging_dir)
        manifest = verify_project(project_dir)
        if tags.get("content_sha256") != content_sha256(project_dir):
            raise ValueError(f"pulled project differs from the registered content hash [{tags.get('content_sha256')}]")
        shutil.rmtree(dest_dir, ignore_errors=True)
        shutil.copytree(project_dir, dest_dir)
        return manifest
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def render_rust(signature):
    required_inputs = [entry["name"] for entry in signature["inputs"] if entry["parameters"]["required"]]
    required_outputs = [entry["name"] for entry in signature["outputs"] if entry["parameters"]["required"]]
    lines = [
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


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fix_hints(rules):
    hints = []
    for rule in rules:
        hint = PROJECT_FIX_HINTS.get(rule) or PROJECT_FIX_HINTS.get(rule[:2])
        if hint and hint not in hints:
            hints.append(hint)
    return hints


def main(arguments=None):
    parser = argparse.ArgumentParser(prog="asystem.model")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify").add_argument("project_dir")
    commands.add_parser("replay").add_argument("project_dir")
    commands.add_parser("lint").add_argument("project_dir")
    generate = commands.add_parser("generate")
    generate.add_argument("project_dir")
    generate.add_argument("--rust")
    check_release_parser = commands.add_parser("check-release")
    check_release_parser.add_argument("project_dir")
    check_release_parser.add_argument("--source-dir")
    changed = commands.add_parser("changed")
    changed.add_argument("workspace_dir")
    changed.add_argument("pins_path")
    check_metadata = commands.add_parser("check-metadata")
    check_metadata.add_argument("workspace_dir")
    check_metadata.add_argument("pins_path")
    check_metadata.add_argument("source_dir")
    release = commands.add_parser("release")
    release.add_argument("source_dir")
    release.add_argument("--version", required=True)
    release.add_argument("--by", required=True)
    release.add_argument("--mlserver")
    publish = commands.add_parser("publish")
    publish.add_argument("source_dir")
    publish.add_argument("--mlserver")
    status = commands.add_parser("status")
    status.add_argument("source_dir")
    status.add_argument("--mlserver")
    embed = commands.add_parser("embed")
    embed.add_argument("consumer_dir")
    embed.add_argument("source_dir")
    embed.add_argument("name")
    options = parser.parse_args(arguments)

    def hints(rules):
        for hint in fix_hints(rules):
            print(f"HINT {hint}", file=sys.stderr)

    def hints_in(text):
        hints(re.findall(r"\b((?:PJ|NB|WS|PM|AC|CP|RP|MD)\d{3})\b", text))

    try:
        if options.command == "verify":
            print(f"verified model [{verify_project(options.project_dir)['name']}]")
        elif options.command == "lint":
            findings = lint_project(options.project_dir)
            for rule, message in findings:
                print(f"{options.project_dir} {rule} {message}", file=sys.stderr)
            hints(rule for rule, _ in findings)
            return 1 if findings else 0
        elif options.command == "changed":
            from asystem.metadata import inputs_changed

            with open(join(options.workspace_dir, "notebook.ipynb")) as notebook_file:
                packages = any(cell["cell_type"] == "code" and "package_project(" in "".join(cell["source"]) for cell in json.load(notebook_file)["cells"])
            if not packages:
                print("unpackaged")
            else:
                print("changed" if inputs_changed(options.workspace_dir, options.pins_path) else "unchanged")
        elif options.command == "check-metadata":
            from asystem.metadata import PROJECT_DIR, lint_metadata

            with open(join(options.workspace_dir, PROJECT_DIR, PROJECT_MANIFEST)) as manifest_file:
                findings = lint_metadata(options.workspace_dir, json.load(manifest_file)["flavour"], options.pins_path, options.source_dir)
            for rule, message in findings:
                print(f"{options.workspace_dir} {rule} {message}", file=sys.stderr)
            hints(rule for rule, _ in findings)
            return 1 if findings else 0
        elif options.command == "release":
            from asystem.release import release_workspaces, stale_consumers

            tracking_uri = registry_address(os.environ.get("MLFLOW_TRACKING_URI"))
            released = release_workspaces(options.source_dir, options.version, options.by, tracking_uri, options.mlserver)
            print(f"released workspaces {released}")
            for consumer in stale_consumers(options.source_dir):
                print(f"WARN consumer embeds an older release [{relpath(consumer, options.source_dir)}]", file=sys.stderr)
        elif options.command == "publish":
            from asystem.metadata import read_metadata
            from asystem.release import publish_workspace, workspaces

            tracking_uri = registry_address(os.environ.get("MLFLOW_TRACKING_URI"))
            for name, directory in workspaces(options.source_dir).items():
                metadata = read_metadata(directory) if isfile(join(directory, "metadata.json")) else None
                if metadata is not None and metadata["released_version"] is not None and any(target["kind"] == "served" for target in metadata["targets"]):
                    print(f"published model [{name}] [{publish_workspace(name, directory, tracking_uri, options.mlserver)}]")
        elif options.command == "status":
            from asystem.release import status_lines

            for level, message in status_lines(options.source_dir, os.environ.get("MLFLOW_TRACKING_URI") and registry_address(os.environ["MLFLOW_TRACKING_URI"]), options.mlserver):
                print(f"{level} {message}", file=sys.stderr)
        elif options.command == "embed":
            from asystem.release import embed_consumer

            print(f"embed [{embed_consumer(options.consumer_dir, options.source_dir, options.name)}] consumer [{options.consumer_dir}]")
        elif options.command == "check-release":
            findings = check_release(options.project_dir)
            if options.source_dir:
                from asystem.release import slot_findings

                findings = [*findings, *slot_findings(options.project_dir, options.source_dir)]
            for rule, message in findings:
                print(f"{options.project_dir} {rule} {message}", file=sys.stderr)
            hints(rule for rule, _ in findings)
            return 1 if findings else 0
        elif options.command == "replay":
            from asystem.replay import replay_project

            findings = replay_project(options.project_dir)
            for rule, message in findings:
                print(f"ERROR {rule} {message}", file=sys.stderr)
            hints(rule for rule, _ in findings)
            if findings:
                return 1
            print(f"replayed project [{options.project_dir}]")
        elif options.command == "generate":
            with open(join(options.project_dir, PROJECT_SIGNATURE)) as signature_file:
                signature = json.load(signature_file)
            if options.rust:
                _write_text(options.rust, render_rust(signature))
    except GateError as error:
        print(f"FAILED stage [{error.stage}] gate [{error.gate}] [{error.cause}]", file=sys.stderr)
        hints_in(error.cause)
        return 1
    except (ValueError, KeyError, OSError) as error:
        print(f"ERROR model command failed [{options.command}] [{error}]", file=sys.stderr)
        hints_in(str(error))
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


def _not_found(error):
    return error.error_code == "RESOURCE_DOES_NOT_EXIST" or "not found" in str(error.message)


def _acceptance_outcome(value, limit, direction):
    if value is None:
        return False, None
    if direction == "max":
        return value <= limit, (max(value, 0) / limit if limit > 0 else (0.0 if value <= 0 else None))
    return value >= limit, (limit / value if value > 0 else None)


def _acceptance_budget(checks):
    budgets = [entry.get("budget") for entry in checks if entry.get("gate") is True]
    return None if not budgets or any(budget is None for budget in budgets) else max(budgets)


def _lint_evaluation(project_dir, files, signature):
    evaluation_path = join(project_dir, files["evaluation"]["path"])
    if not isfile(evaluation_path):
        return []
    with open(evaluation_path) as evaluation_file:
        evaluation = json.load(evaluation_file)
    findings = []
    outputs = {entry["name"]: entry for entry in signature["outputs"]}
    entries = evaluation.get("checks", [])
    for entry in entries:
        label = f"split [{entry.get('split')}] output [{entry.get('output')}] check [{entry.get('name')}]"
        if entry.get("split") not in ACCEPTANCE_SPLITS:
            findings.append(("AC002", f"acceptance split is not one of {list(ACCEPTANCE_SPLITS)} {label}"))
        if not isinstance(entry.get("name"), str) or not PROJECT_NAME.match(entry["name"]):
            findings.append(("AC002", f"acceptance check name must follow the naming style {label}"))
        if entry.get("output") not in outputs:
            findings.append(("AC002", f"acceptance output is not in the signature {label}"))
        value, limit, direction = entry.get("value"), entry.get("limit"), entry.get("direction")
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
            findings.append(("AC002", f"acceptance value must be a number or null {label}"))
        elif direction not in ACCEPTANCE_DIRECTIONS or isinstance(limit, bool) or not isinstance(limit, (int, float)) or limit < 0 or (direction == "min" and limit <= 0):
            findings.append(("AC002", f"acceptance direction must be one of {list(ACCEPTANCE_DIRECTIONS)} with a limit that is positive for min {label}"))
        elif (entry.get("passed"), entry.get("budget")) != _acceptance_outcome(value, limit, direction):
            findings.append(("AC003", f"acceptance outcome does not follow from the value and limit {label}"))
        if not isinstance(entry.get("gate"), bool):
            findings.append(("AC002", f"acceptance gate must be true or false {label}"))
    gated = {entry.get("output") for entry in entries if entry.get("gate") is True}
    required = {name for name, entry in outputs.items() if entry["shape"] == [1] and entry["parameters"]["required"]}
    findings.extend(("AC001", f"no gating acceptance check for required output [{name}]") for name in sorted(required - gated))
    datasets = evaluation.get("datasets", {})
    findings.extend(("AC003", f"the evaluation has no dataset hashes for split [{split}]") for split in sorted({entry.get("split") for entry in entries} - set(datasets)))
    findings.extend(
        ("AC003", f"a check was measured on split [{split}] with no dataset recorded")
        for split in sorted({entry.get("split") for entry in entries if entry.get("value") is not None and not datasets.get(entry.get("split"))})
    )
    if evaluation.get("passed") is not all(entry.get("passed") is True for entry in entries if entry.get("gate") is True) or evaluation.get("budget") != _acceptance_budget(entries):
        findings.append(("AC003", "the evaluation verdict and budget do not match its checks"))
    return findings


def _rust_type(entry):
    base = {"FP64": "f64", "INT64": "i64"}[entry["datatype"]]
    return f"Vec<{base}>" if entry["shape"] == [-1] else base


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
    if manifest.get("flavour") == "static":
        required = {entry["name"] for entry in signature["outputs"] if entry["parameters"]["required"]}
        findings.extend(("PJ008", f"a static project must give a constant for the required output [{missing}]") for missing in sorted(required - set(constants)))
    return findings


def _lint_golden(manifest, signature, golden):
    findings = []
    input_specs = {entry["name"]: entry for entry in signature["inputs"]}
    output_specs = {entry["name"]: entry for entry in signature["outputs"]}
    required_inputs = {name for name, entry in input_specs.items() if entry["parameters"]["required"]}
    required_outputs = {name for name, entry in output_specs.items() if entry["parameters"]["required"]}
    state_inputs = {name for name, entry in input_specs.items() if entry["shape"] == [-1]}
    constants = manifest.get("constants", {})
    for name, bounds in golden.get("tolerance", {}).items():
        spec = output_specs.get(name)
        if spec is None or spec["datatype"] != "FP64":
            findings.append(("PJ015", f"tolerance names an output that is not an FP64 signature output [{name}]"))
        elif (
            not isinstance(bounds, dict)
            or not bounds
            or set(bounds) - {"absolute", "relative"}
            or any(isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 for value in bounds.values())
        ):
            findings.append(("PJ015", f"tolerance for output [{name}] must give a non-negative absolute or relative bound"))
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
        if manifest.get("flavour") == "static":
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


def _wasm_module_imports(path):
    import wasmtime

    with open(path, "rb") as model_file:
        return wasmtime.Module(wasmtime.Engine(), model_file.read()).imports


def _write_json(path, document):
    with open(path, "w") as file:
        json.dump(document, file, indent=2, sort_keys=False)
        file.write("\n")


if __name__ == "__main__":
    sys.exit(main())
