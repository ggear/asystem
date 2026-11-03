import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from os.path import abspath, basename, dirname, isdir, isfile, join, relpath

PROJECT_SPEC_VERSION = 1
CONSUMER_MODEL_PATH = "src/build/resources/model"
PROJECT_MANIFEST = "project.json"
PROJECT_SIGNATURE = "signature.json"
PROJECT_GOLDEN = "golden.json"
PROJECT_EVALUATION = "evaluation.json"
PROJECT_VERSION_FILE = ".version"
PROJECT_VERSION_FIRST = 1000
PROJECT_VERSION_SENTINEL = "0000-SNAPSHOT"
PROJECT_VERSION_HIGH_WATER = "model_version_high_water"
PROJECT_VERSION_ALIAS = re.compile(r"^m(\d{4,})$")
PROJECT_VERSION_PLACEHOLDER = re.compile(r"^\d{4,}-SNAPSHOT$")
PROJECT_VERSION_PROMOTED = re.compile(r"^\d{4,}$")
PROJECT_VERSION_STATIC = re.compile(r"^static-\d+$")
PROJECT_RELEASE_TAG = re.compile(r"^\d+\.\d+\.\d+$")
PROJECT_STAMP_LINE = re.compile(r'^MODEL_VERSION = "([^"]*)"$', re.MULTILINE)
PROJECT_STAMP_SECTION = "asystem.model_version"
PROJECT_STAMPED = ("wasm", "onnx", "pyfunc")
PROJECT_REGISTRY_TAGS = ("model_version", "service_version", "project_sha256", "project_flavor", "acceptance", "acceptance_budget", "reviewed_by")
WASM_HEADER = b"\0asm\x01\x00\x00\x00"
ACCEPTANCE_SPLITS = ("validation", "backtest")
ACCEPTANCE_DIRECTIONS = ("max", "min")
ACCEPTANCE_BUDGET = 1.0
PROJECT_FLAVORS = ("static", "wasm", "onnx", "pyfunc")
PROJECT_PLACEHOLDERS = ("tbd", "todo", "unknown", "none", "n/a", "not applicable", "to be determined")
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


def package_project(project_dir, name, model_version, flavor, signature, samples, provenance, constants=None, model_path=None, sequence="golden", evaluation=None):
    golden = golden_from_samples(signature, model_version, samples, sequence, constants)
    return write_project(project_dir, name, model_version, flavor, signature, golden, provenance, constants, model_path, evaluation=evaluation)


def write_project(project_dir, name, model_version, flavor, signature, golden, provenance, constants=None, model_path=None, onnx=None, evaluation=None):
    os.makedirs(project_dir, exist_ok=True)
    files = {"signature": PROJECT_SIGNATURE, "golden": PROJECT_GOLDEN}
    if evaluation is not None:
        _write_json(join(project_dir, PROJECT_EVALUATION), evaluation)
        files["evaluation"] = PROJECT_EVALUATION
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
    if flavor in PROJECT_FLAVORS and flavor != "static":
        implementation = provenance.get("implementation")
        if not isinstance(implementation, str) or len(implementation.split()) < 2 or implementation.strip().lower() in PROJECT_PLACEHOLDERS:
            findings.append(("PJ002", f"provenance implementation must say what is inside the model for flavor [{flavor}]"))
    files = manifest.get("files", {})
    findings.extend(("PJ003", f"file missing from manifest [{key}]") for key in ("signature", "golden", *PROJECT_REQUIRED_FILES.get(flavor, ())) if key not in files)
    for key, entry in files.items():
        file_path = join(project_dir, entry["path"])
        if not isfile(file_path):
            findings.append(("PJ003", f"file absent [{key}] path [{entry['path']}]"))
        elif file_sha256(file_path) != entry["sha256"]:
            findings.append(("PJ003", f"file checksum mismatch [{key}] path [{entry['path']}]"))
    if flavor == "static" and not PROJECT_VERSION_STATIC.match(str(manifest.get("model_version"))):
        findings.append(("PJ014", f"a static project's model version must be static-<number>, found [{manifest.get('model_version')}]"))
    if flavor in PROJECT_STAMPED and "model" in files and isfile(join(project_dir, files["model"]["path"])):
        try:
            stamp = read_stamp(join(project_dir, files["model"]["path"]), flavor)
        except ValueError as error:
            findings.append(("PJ013", str(error)))
        else:
            if stamp != str(manifest.get("model_version")):
                findings.append(("PJ013", f"model stamp [{stamp}] differs from the manifest model version [{manifest.get('model_version')}]"))
    if "signature" not in files or not isfile(join(project_dir, files["signature"]["path"])):
        return findings
    with open(join(project_dir, files["signature"]["path"])) as signature_file:
        signature = json.load(signature_file)
    findings.extend(_lint_signature(manifest, signature))
    if "evaluation" in files:
        findings.extend(_lint_evaluation(project_dir, files, signature))
    elif flavor in PROJECT_FLAVORS and flavor != "static":
        findings.append(("AC001", f"a project of flavor [{flavor}] needs an acceptance evaluation"))
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
    import mlflow.pyfunc

    import mlflow
    from mlflow import MlflowClient

    manifest = verify_project(project_dir)
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(tracking_uri)
    client = MlflowClient()
    static = manifest["flavor"] == "static"
    content_sha256 = project_content_sha256(project_dir)
    model_version = str(manifest["model_version"]) if static else str(next_model_version(client, name))
    version = next(
        (
            candidate
            for candidate in client.search_model_versions(f"name = '{name}'")
            if candidate.tags.get("content_sha256") == content_sha256 and candidate.tags.get("model_version") == model_version
        ),
        None,
    )
    if version is None:
        with tempfile.TemporaryDirectory(prefix=f"{name}-register-") as staging_dir:
            staged_dir = project_dir if static else join(staging_dir, "project")
            if not static:
                manifest = restamp_project(project_dir, model_version, staged_dir)
            mlflow.set_experiment(name)
            with mlflow.start_run() as run:
                mlflow.set_tags({"project_flavor": manifest["flavor"], "project_model_version": model_version})
                if "evaluation" in manifest["files"]:
                    import pandas
                    from mlflow.data.pandas_dataset import from_pandas

                    with open(join(staged_dir, PROJECT_EVALUATION)) as evaluation_file:
                        evaluation = json.load(evaluation_file)
                    mlflow.set_tags({"acceptance": "passed" if evaluation["passed"] else "failed", "acceptance_budget": str(evaluation["budget"])})
                    mlflow.log_metrics({"acceptance_passed": float(evaluation["passed"]), **({"acceptance_budget": evaluation["budget"]} if evaluation["budget"] is not None else {})})
                    mlflow.log_metrics({f"{entry['split']}/{entry['output']}/{entry['name']}": entry["value"] for entry in evaluation["checks"] if entry["value"] is not None})
                    for split, entries in evaluation["datasets"].items():
                        for entry in entries:
                            dataset = from_pandas(pandas.DataFrame(), name=os.path.splitext(basename(entry["path"]))[0], digest=entry["sha256"][:16])
                            mlflow.log_input(dataset, context=split)
                if manifest["flavor"] == "pyfunc":
                    from mlflow.models import ModelSignature
                    from mlflow.types import ColSpec, Schema

                    with open(join(staged_dir, manifest["files"]["signature"]["path"])) as signature_file:
                        signature = json.load(signature_file)
                    column_types = {"FP64": "double", "INT64": "long"}

                    def schema(entries):
                        for entry in entries:
                            if entry["datatype"] not in column_types or entry["shape"] != [1]:
                                raise ValueError(f"pyfunc signature supports scalar FP64 and INT64 only [{entry['name']}]")
                        return Schema([ColSpec(column_types[entry["datatype"]], entry["name"]) for entry in entries])

                    mlflow.pyfunc.log_model(
                        name="project",
                        python_model=join(staged_dir, manifest["files"]["model"]["path"]),
                        artifacts={"project": staged_dir},
                        signature=ModelSignature(inputs=schema(signature["inputs"]), outputs=schema(signature["outputs"])),
                    )
                else:
                    mlflow.log_artifacts(staged_dir, artifact_path="project")
            if manifest["flavor"] == "pyfunc":
                version = mlflow.register_model(f"runs:/{run.info.run_id}/project", name)
            else:
                if not client.search_registered_models(filter_string=f"name = '{name}'"):
                    client.create_registered_model(name)
                version = client.create_model_version(name, f"{run.info.artifact_uri}/project", run_id=run.info.run_id)
            for key, value in {
                "content_sha256": content_sha256,
                "model_version": model_version,
                "project_flavor": manifest["flavor"],
                "project_sha256": file_sha256(join(staged_dir, PROJECT_MANIFEST)),
            }.items():
                client.set_model_version_tag(name, version.version, key, value)
    for alias in aliases:
        client.set_registered_model_alias(name, alias, version.version)
    return version.version


def read_stamp(path, flavor):
    if flavor == "pyfunc":
        with open(path) as model_file:
            stamps = PROJECT_STAMP_LINE.findall(model_file.read())
        if len(stamps) != 1:
            raise ValueError(f'model file needs exactly one line MODEL_VERSION = "..." [{path}]')
        return stamps[0]
    if flavor == "wasm":
        with open(path, "rb") as model_file:
            stamps = [data for name, data in _wasm_custom_sections(model_file.read()) if name == PROJECT_STAMP_SECTION]
        if len(stamps) != 1:
            raise ValueError(f"model file needs exactly one custom section [{PROJECT_STAMP_SECTION}] [{path}]")
        return stamps[0].decode()
    if flavor == "onnx":
        import onnx

        stamps = [entry.value for entry in onnx.load(path).metadata_props if entry.key == PROJECT_STAMP_SECTION]
        if len(stamps) != 1:
            raise ValueError(f"model file needs exactly one metadata property [{PROJECT_STAMP_SECTION}] [{path}]")
        return stamps[0]
    raise ValueError(f"stamping is not built for flavor [{flavor}]")


def stamp_model(path, flavor, version):
    stamped = _stamped_bytes(path, flavor, version)
    with open(path, "wb") as model_file:
        model_file.write(stamped)


def content_sha256(path, flavor):
    return hashlib.sha256(_stamped_bytes(path, flavor, PROJECT_VERSION_SENTINEL)).hexdigest()


def restamp_project(project_dir, model_version, dest_dir):
    manifest = verify_project(project_dir)
    flavor = manifest["flavor"]
    if flavor not in PROJECT_STAMPED and flavor != "static":
        raise ValueError(f"stamping is not built for flavor [{flavor}]")
    shutil.rmtree(dest_dir, ignore_errors=True)
    shutil.copytree(project_dir, dest_dir)
    if flavor in PROJECT_STAMPED:
        stamp_model(join(dest_dir, manifest["files"]["model"]["path"]), flavor, model_version)
    signature_path, golden_path = join(dest_dir, manifest["files"]["signature"]["path"]), join(dest_dir, manifest["files"]["golden"]["path"])
    with open(signature_path) as signature_file, open(golden_path) as golden_file:
        signature, golden = json.load(signature_file), json.load(golden_file)
    signature["versions"] = [model_version]
    golden["model_version"] = model_version
    for sequence in golden["sequences"]:
        for step in sequence["steps"]:
            if "response" in step:
                step["response"]["model_version"] = model_version
    _write_json(signature_path, signature)
    _write_json(golden_path, golden)
    manifest["model_version"] = model_version
    manifest["files"] = {key: {"path": entry["path"], "sha256": file_sha256(join(dest_dir, entry["path"]))} for key, entry in manifest["files"].items()}
    _write_json(join(dest_dir, PROJECT_MANIFEST), manifest)
    return verify_project(dest_dir)


def project_content_sha256(project_dir):
    manifest = verify_project(project_dir)
    if manifest["flavor"] == "static":
        return file_sha256(join(project_dir, PROJECT_MANIFEST))
    with tempfile.TemporaryDirectory(prefix="content-") as staging_dir:
        restamp_project(project_dir, PROJECT_VERSION_SENTINEL, join(staging_dir, "project"))
        return file_sha256(join(staging_dir, "project", PROJECT_MANIFEST))


def next_model_version(client, name):
    from mlflow.exceptions import MlflowException

    try:
        model = client.get_registered_model(name)
    except MlflowException as error:
        if _not_found(error):
            return PROJECT_VERSION_FIRST
        raise
    promoted = [int(match.group(1)) for alias in model.aliases if (match := PROJECT_VERSION_ALIAS.match(alias))]
    return max(PROJECT_VERSION_FIRST - 1, int(model.tags.get(PROJECT_VERSION_HIGH_WATER, 0)), *promoted) + 1


def service_version(repo_dir=None):
    directory = repo_dir if repo_dir is not None else dirname(abspath(__file__))
    try:
        result = subprocess.run(["git", "-C", directory, "tag", "--list", "--sort=-v:refname"], capture_output=True, text=True, timeout=30, check=True)
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError(f"no release tag could be read [{directory}] [{error}]") from error
    tags = [tag for tag in result.stdout.split() if PROJECT_RELEASE_TAG.match(tag)]
    if not tags:
        raise ValueError(f"no release tag in [{directory}]")
    return tags[0]


def resolve_model(name, selector, tracking_uri):
    from mlflow.exceptions import MlflowException

    import mlflow
    from mlflow import MlflowClient

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(tracking_uri)
    client = MlflowClient()
    alias = _selector_alias(client, name, selector)
    if alias is None:
        return None
    try:
        version = client.get_model_version_by_alias(name, alias)
    except MlflowException as error:
        if _not_found(error):
            return None
        raise
    return {"name": name, "alias": alias, "registry_version": version.version, **{key: version.tags.get(key) for key in PROJECT_REGISTRY_TAGS}}


def list_models(tracking_uri):
    import mlflow
    from mlflow import MlflowClient

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(tracking_uri)
    client = MlflowClient()
    rows = []
    for model in client.search_registered_models():
        promoted = sorted(int(match.group(1)) for alias in model.aliases if (match := PROJECT_VERSION_ALIAS.match(alias)))
        release = client.get_model_version(model.name, model.aliases["release"]) if "release" in model.aliases else None
        rows.append(
            {
                "name": model.name,
                "release": release.tags.get("model_version") if release is not None else None,
                "latest": str(promoted[-1]) if promoted else None,
                "service_version": release.tags.get("service_version") if release is not None else None,
                "flavor": release.tags.get("project_flavor") if release is not None else None,
            }
        )
    return sorted(rows, key=lambda row: row["name"])


def slot_versions(source_dir):
    rows = []
    for slot in ("default", "release"):
        for manifest_path in sorted(glob.glob(join(source_dir, "*", "*", CONSUMER_MODEL_PATH, slot, PROJECT_MANIFEST))):
            with open(manifest_path) as manifest_file:
                manifest = json.load(manifest_file)
            rows.append({"slot": relpath(dirname(manifest_path), source_dir), "name": manifest["name"], "flavor": manifest["flavor"], "model_version": str(manifest["model_version"])})
    return rows


def compare_project(output_dir, committed_dir):
    output, committed = verify_project(output_dir), verify_project(committed_dir)
    findings = []
    if output["flavor"] == "static" and committed["flavor"] == "static":
        differing = sorted(key for key in output["files"].keys() | committed["files"].keys() if output["files"].get(key) != committed["files"].get(key))
        if differing or {key: value for key, value in output.items() if key != "files"} != {key: value for key, value in committed.items() if key != "files"}:
            findings.append(("CP001", f"the static project differs from the committed one in files {differing}"))
        return findings
    with open(join(output_dir, PROJECT_SIGNATURE)) as output_file, open(join(committed_dir, PROJECT_SIGNATURE)) as committed_file:
        findings.extend(("CP002", difference) for difference in diff_signature(json.load(committed_file), json.load(output_file)))
    verdicts = []
    for directory in (output_dir, committed_dir):
        evaluation_path = join(directory, PROJECT_EVALUATION)
        if isfile(evaluation_path):
            with open(evaluation_path) as evaluation_file:
                verdicts.append(json.load(evaluation_file)["passed"])
        else:
            verdicts.append(None)
    if verdicts[0] != verdicts[1]:
        findings.append(("CP003", f"the acceptance verdict is [{verdicts[0]}] and the committed one is [{verdicts[1]}]"))
    return findings


def check_release(project_dir):
    verify_project(project_dir)
    return check_acceptance(project_dir)


def pull_model(name, selector, dest_dir, tracking_uri, signature_path=None, unpromoted=False):
    from mlflow.artifacts import download_artifacts
    from mlflow.exceptions import MlflowException

    import mlflow
    from mlflow import MlflowClient

    if not unpromoted and selector not in ("release", "latest") and not PROJECT_VERSION_PROMOTED.match(selector):
        raise ValueError(f"only a promoted version may be pulled, not [{selector}]")
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(tracking_uri)
    client = MlflowClient()
    alias = _selector_alias(client, name, selector)
    if alias is None:
        return None
    staging_dir = tempfile.mkdtemp(prefix=f"{name}-")
    try:
        try:
            download_artifacts(artifact_uri=f"models:/{name}@{alias}", dst_path=staging_dir)
            tags = client.get_model_version_by_alias(name, alias).tags
        except MlflowException as error:
            if _not_found(error):
                return None
            raise
        project_dir = _find_project_dir(staging_dir)
        manifest = verify_project(project_dir)
        expected = tags.get("model_version")
        if PROJECT_VERSION_PROMOTED.match(selector) and expected != selector:
            raise ValueError(f"alias [{alias}] is for model version [{expected}] and not [{selector}]")
        if manifest["flavor"] in PROJECT_STAMPED and expected is not None and str(manifest["model_version"]) != expected:
            raise ValueError(f"pulled model version [{manifest['model_version']}] differs from the registered one [{expected}]")
        if not unpromoted:
            unaccepted = check_acceptance(project_dir)
            if unaccepted:
                raise ValueError("; ".join(f"{rule} {message}" for rule, message in unaccepted))
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


def promote_project(name, tracking_uri, gate_path, hosts, archs, reviewed_by, workspaces_dir=None, released=None):
    from mlflow import MlflowClient

    staging_dir = tempfile.mkdtemp(prefix=f"{name}-promote-")
    try:
        project_dir = join(staging_dir, "project")
        manifest = pull_model(name, PROJECT_ALIAS_CANDIDATE, project_dir, tracking_uri, unpromoted=True)
        if manifest is None:
            raise ValueError(f"no registered model [{name}] with alias [{PROJECT_ALIAS_CANDIDATE}]")
        with open(gate_path) as gate_file:
            gate = json.load(gate_file)
        client = MlflowClient()
        findings = check_gate(gate, file_sha256(join(project_dir, PROJECT_MANIFEST)), hosts, archs, reviewed_by)
        findings.extend(check_acceptance(project_dir))
        number = str(manifest["model_version"])
        evaluation = {"budget": None}
        if isfile(join(project_dir, PROJECT_EVALUATION)):
            with open(join(project_dir, PROJECT_EVALUATION)) as evaluation_file:
                evaluation = json.load(evaluation_file)
        if manifest["flavor"] == "static":
            findings.append(("PM005", "a static project has no numbered model version to promote"))
        elif number != str(next_model_version(client, name)):
            findings.append(("PM005", f"the candidate is stamped [{number}] and the next model version is [{next_model_version(client, name)}], register it again"))
        try:
            released = released if released is not None else service_version()
        except ValueError as error:
            findings.append(("PM006", f"no release version could be recorded [{error}]"))
        if findings:
            raise ValueError("; ".join(f"{rule} {message}" for rule, message in findings))
        version = client.get_model_version_by_alias(name, PROJECT_ALIAS_CANDIDATE).version
        for alias in (f"m{number}", PROJECT_ALIAS_RELEASE):
            client.set_registered_model_alias(name, alias, version)
        for key, value in {"service_version": released, "reviewed_by": reviewed_by, "acceptance": "passed", "acceptance_budget": str(evaluation["budget"])}.items():
            client.set_model_version_tag(name, version, key, value)
        client.set_registered_model_tag(name, PROJECT_VERSION_HIGH_WATER, number)
        workspace = _find_workspace(workspaces_dir, name) if workspaces_dir else None
        if workspace is not None:
            with open(join(workspace, PROJECT_VERSION_FILE), "w") as version_file:
                version_file.write(f"{int(number) + 1}-SNAPSHOT\n")
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
    pull.add_argument("selector")
    pull.add_argument("dest_dir")
    pull.add_argument("--signature")
    resolve = commands.add_parser("resolve")
    resolve.add_argument("name")
    resolve.add_argument("selector")
    commands.add_parser("list")
    status = commands.add_parser("status")
    status.add_argument("source_dir")
    commands.add_parser("verify").add_argument("project_dir")
    commands.add_parser("replay").add_argument("project_dir")
    gate = commands.add_parser("gate")
    gate.add_argument("project_dir")
    gate.add_argument("--out", required=True)
    commands.add_parser("lint").add_argument("project_dir")
    generate = commands.add_parser("generate")
    generate.add_argument("project_dir")
    generate.add_argument("--rust")
    generate.add_argument("--go")
    generate.add_argument("--go-package", default="model")
    compare = commands.add_parser("compare")
    compare.add_argument("output_dir")
    compare.add_argument("committed_dir")
    commands.add_parser("check-release").add_argument("project_dir")
    promote = commands.add_parser("promote")
    promote.add_argument("name")
    promote.add_argument("--gate", required=True)
    promote.add_argument("--hosts", default="python,rust,go")
    promote.add_argument("--archs", default="x86_64,aarch64")
    promote.add_argument("--reviewed-by", required=True)
    promote.add_argument("--workspaces")
    options = parser.parse_args(arguments)
    try:
        if options.command == "pull":
            manifest = pull_model(options.name, options.selector, options.dest_dir, os.environ["MLFLOW_TRACKING_URI"], options.signature)
            if manifest is None:
                print(f"no registered model [{options.name}] selector [{options.selector}], nothing pulled")
            else:
                print(f"pulled model [{options.name}] selector [{options.selector}] version [{manifest['model_version']}]")
                print(json.dumps(resolve_model(options.name, options.selector, os.environ["MLFLOW_TRACKING_URI"]), sort_keys=True))
        elif options.command == "resolve":
            print(json.dumps(resolve_model(options.name, options.selector, os.environ["MLFLOW_TRACKING_URI"]), sort_keys=True))
        elif options.command == "list":
            for row in list_models(os.environ["MLFLOW_TRACKING_URI"]):
                print(json.dumps(row, sort_keys=True))
        elif options.command == "status":
            registry = {row["name"]: row for row in list_models(os.environ["MLFLOW_TRACKING_URI"])} if os.environ.get("MLFLOW_TRACKING_URI") else {}
            for row in slot_versions(options.source_dir):
                print(json.dumps({**row, "registry_release": registry.get(row["name"], {}).get("release"), "registry_latest": registry.get(row["name"], {}).get("latest")}, sort_keys=True))
        elif options.command == "verify" and isdir(options.project_dir):
            manifest = verify_project(options.project_dir)
            print(f"verified model [{manifest['name']}] version [{manifest['model_version']}]")
        elif options.command == "lint":
            findings = lint_project(options.project_dir)
            for rule, message in findings:
                print(f"{options.project_dir}: {rule} {message}", file=sys.stderr)
            return 1 if findings else 0
        elif options.command in ("compare", "check-release"):
            findings = compare_project(options.output_dir, options.committed_dir) if options.command == "compare" else check_release(options.project_dir)
            for rule, message in findings:
                print(f"{options.committed_dir if options.command == 'compare' else options.project_dir} {rule} {message}", file=sys.stderr)
            return 1 if findings else 0
        elif options.command in ("replay", "gate"):
            from asystem.replay import gate_project

            document, findings = gate_project(options.project_dir)
            for rule, message in findings:
                print(f"ERROR {rule} {message}", file=sys.stderr)
            if options.command == "gate":
                _write_json(options.out, document)
            if findings:
                return 1
            print(f"replayed project [{options.project_dir}]")
        elif options.command == "generate":
            with open(join(options.project_dir, PROJECT_SIGNATURE)) as signature_file:
                signature = json.load(signature_file)
            if options.rust:
                _write_text(options.rust, render_rust(signature))
            if options.go:
                _write_text(options.go, render_go(signature, options.go_package))
        elif options.command == "promote":
            version = promote_project(options.name, os.environ["MLFLOW_TRACKING_URI"], options.gate, options.hosts.split(","), options.archs.split(","), options.reviewed_by, options.workspaces)
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


def _not_found(error):
    return error.error_code == "RESOURCE_DOES_NOT_EXIST" or "not found" in str(error.message)


def _selector_alias(client, name, selector):
    from mlflow.exceptions import MlflowException

    if selector == "latest":
        try:
            aliases = client.get_registered_model(name).aliases
        except MlflowException as error:
            if _not_found(error):
                return None
            raise
        promoted = [int(match.group(1)) for alias in aliases if (match := PROJECT_VERSION_ALIAS.match(alias))]
        return f"m{max(promoted)}" if promoted else None
    return f"m{selector}" if PROJECT_VERSION_PROMOTED.match(selector) else selector


def _find_workspace(workspaces_dir, name):
    for path in sorted(glob.glob(join(workspaces_dir, "*", "*", "*"))):
        parts = relpath(path, workspaces_dir).split(os.sep)
        if all(PROJECT_NAME.match(part) for part in parts) and registered_name(*parts) == name:
            return path
    return None


def _wasm_custom_sections(data):
    if data[:8] != WASM_HEADER:
        raise ValueError("not a WebAssembly module")
    sections, position = [], 8
    while position < len(data):
        section_id = data[position]
        size, position = _leb128_read(data, position + 1)
        payload = data[position : position + size]
        if len(payload) != size:
            raise ValueError("WebAssembly section is truncated")
        position += size
        if section_id == 0:
            name_size, offset = _leb128_read(payload, 0)
            sections.append((payload[offset : offset + name_size].decode(), payload[offset + name_size :]))
    return sections


def _leb128_read(data, position):
    value, shift = 0, 0
    while True:
        if position >= len(data):
            raise ValueError("WebAssembly integer is truncated")
        byte = data[position]
        position += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, position
        shift += 7


def _leb128_write(value):
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _stamped_bytes(path, flavor, version):
    if flavor == "pyfunc":
        with open(path) as model_file:
            text = model_file.read()
        if len(PROJECT_STAMP_LINE.findall(text)) != 1:
            raise ValueError(f'model file needs exactly one line MODEL_VERSION = "..." [{path}]')
        return PROJECT_STAMP_LINE.sub(lambda _: f'MODEL_VERSION = "{version}"', text).encode()
    if flavor == "wasm":
        with open(path, "rb") as model_file:
            data = model_file.read()
        if data[:8] != WASM_HEADER:
            raise ValueError("not a WebAssembly module")
        kept, position = bytearray(WASM_HEADER), 8
        while position < len(data):
            start = position
            section_id = data[position]
            size, payload_start = _leb128_read(data, position + 1)
            position = payload_start + size
            if position > len(data):
                raise ValueError("WebAssembly section is truncated")
            if section_id == 0:
                name_size, offset = _leb128_read(data[payload_start:position], 0)
                if data[payload_start + offset : payload_start + offset + name_size].decode() == PROJECT_STAMP_SECTION:
                    continue
            kept += data[start:position]
        name = PROJECT_STAMP_SECTION.encode()
        payload = _leb128_write(len(name)) + name + version.encode()
        return bytes(kept) + b"\x00" + _leb128_write(len(payload)) + payload
    if flavor == "onnx":
        import onnx

        graph = onnx.load(path)
        kept = [entry for entry in graph.metadata_props if entry.key != PROJECT_STAMP_SECTION]
        del graph.metadata_props[:]
        graph.metadata_props.extend(kept)
        graph.metadata_props.add(key=PROJECT_STAMP_SECTION, value=version)
        return graph.SerializeToString(deterministic=True)
    raise ValueError(f"stamping is not built for flavor [{flavor}]")


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
