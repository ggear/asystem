import json
import os
import shutil
from os.path import basename, dirname, isfile, join

from mlmodels._constants import ACCEPTANCE_DIRECTIONS, MANIFEST_SCHEMA, PROJECT_EVALUATION, PROJECT_GOLDEN, PROJECT_MANIFEST, PROJECT_MODEL_FILES, PROJECT_SCHEMA, PROJECT_SIGNATURE
from mlmodels._document import write_json
from mlmodels._errors import GateError
from mlmodels._lint_project import acceptance_budget, acceptance_outcome, file_sha256, verify_project, wasm_module_imports
from mlmodels._signature import golden_from_samples


def evaluation_build(check, datasets):
    entries = check()
    if not isinstance(entries, list) or not entries:
        raise ValueError("the acceptance check must return a non-empty list of checks")
    checks = []
    for entry in entries:
        direction, limit, value = entry.get("direction"), entry.get("limit"), entry.get("value")
        if direction not in ACCEPTANCE_DIRECTIONS or isinstance(limit, bool) or not isinstance(limit, (int, float)) or (direction == "min" and limit <= 0) or limit < 0:
            raise ValueError(f"an acceptance check needs a direction of {list(ACCEPTANCE_DIRECTIONS)} and a limit that is positive for min [{entry.get('name')}]")
        passed, budget = acceptance_outcome(value, limit, direction)
        checks.append({**entry, "gate": entry.get("gate", True), "passed": passed, "budget": budget})
    return {
        "schema": PROJECT_SCHEMA,
        "passed": all(entry["passed"] for entry in checks if entry["gate"]),
        "budget": acceptance_budget(checks),
        "independent": "backtest" in datasets,
        "datasets": {
            split: [
                {"path": f"{basename(dirname(path))}/{basename(path)}", "sha256": file_sha256(path), **({"rows": rows} if rows is not None else {})}
                for path, rows in sorted((item if isinstance(item, tuple) else (item, None)) for item in members)
            ]
            for split, members in datasets.items()
        },
        "checks": checks,
    }


def check_acceptance(project_dir):
    evaluation_path = join(project_dir, PROJECT_EVALUATION)
    if not isfile(evaluation_path):
        with open(join(project_dir, PROJECT_MANIFEST)) as manifest_file:
            if json.load(manifest_file)["flavour"] == "static":
                return []
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


def write_project(project_dir, name, flavour, signature, golden, provenance, constants=None, model_path=None, onnx=None, evaluation=None, python_deps=None, model_id=None):
    os.makedirs(project_dir, exist_ok=True)
    files = [PROJECT_SIGNATURE, PROJECT_GOLDEN]
    model_file = None
    if evaluation is not None:
        write_json(join(project_dir, PROJECT_EVALUATION), evaluation)
        files.append(PROJECT_EVALUATION)
    if model_path is not None:
        if flavour not in PROJECT_MODEL_FILES:
            raise ValueError(f"flavour [{flavour}] has no model file")
        model_file = PROJECT_MODEL_FILES[flavour]
        shutil.copy(model_path, join(project_dir, model_file))
        files.append(model_file)
    write_json(join(project_dir, PROJECT_SIGNATURE), signature)
    write_json(join(project_dir, PROJECT_GOLDEN), golden)
    if python_deps and flavour != "pyfunc":
        raise ValueError(f"flavour [{flavour}] takes no python dependencies")
    manifest = {"schema": MANIFEST_SCHEMA, "name": name, "flavour": flavour}
    if model_id is not None:
        manifest["model_id"] = model_id
    if model_file is not None:
        manifest["model"] = model_file
    if constants is not None:
        manifest["constants"] = constants
    if flavour == "pyfunc":
        manifest["runtime"] = {"python": sorted(set(python_deps or ()))}
    if flavour == "wasm" and model_path is not None:
        manifest["runtime"] = {"wasm": sorted({str(entry.name) for entry in wasm_module_imports(model_path)})}
    manifest["provenance"] = provenance
    if onnx is not None:
        manifest["onnx"] = onnx
    manifest["files"] = {file_name: file_sha256(join(project_dir, file_name)) for file_name in files}
    write_json(join(project_dir, PROJECT_MANIFEST), manifest)
    verified = verify_project(project_dir)
    if evaluation is not None and not evaluation["passed"]:
        raise GateError("Evaluate", "acceptance", "; ".join(f"{rule} {message}" for rule, message in check_acceptance(project_dir)))
    return verified


def write_text(path, text):
    with open(path, "w") as target:
        target.write(text)
    print(f"Wrote [{path}]")
