import ast
import hashlib
import json
import re
import sys
from os.path import isfile, join

from mlmodels._constants import (
    ACCEPTANCE_DIRECTIONS,
    ACCEPTANCE_SPLITS,
    FOLD_KEYS,
    FOLD_SCHEMES,
    MANIFEST_SCHEMA,
    PROJECT_DATATYPES,
    PROJECT_EVALUATION,
    PROJECT_FIX_HINTS,
    PROJECT_FLAVOURS,
    PROJECT_GOLDEN,
    PROJECT_MANIFEST,
    PROJECT_MODEL_FILES,
    PROJECT_NAME,
    PROJECT_PLACEHOLDERS,
    PROJECT_RELEASE,
    PROJECT_SCHEMA,
    PROJECT_SIGNATURE,
    PROJECT_SIGNATURE_ERROR,
    PROJECT_SOURCES,
    PROJECT_UNIT_SUFFIXES,
    PYFUNC_BASE_IMPORTS,
    PYFUNC_IMPORT_NAMES,
    WASM_MATH_FUNCTIONS,
    WASM_MATH_MODULE,
)
from mlmodels._errors import GateError


def lint_project(project_dir):
    findings = []
    manifest_path = join(project_dir, PROJECT_MANIFEST)
    if not isfile(manifest_path):
        return [("PJ001", f"manifest missing [{manifest_path}]")]
    with open(manifest_path) as manifest_file:
        manifest = json.load(manifest_file)
    for file_name in (PROJECT_MANIFEST, PROJECT_SIGNATURE, PROJECT_GOLDEN, PROJECT_EVALUATION):
        document_path = join(project_dir, file_name)
        if isfile(document_path):
            with open(document_path) as document_file:
                document = json.load(document_file)
            expected = MANIFEST_SCHEMA if file_name == PROJECT_MANIFEST else PROJECT_SCHEMA
            if next(iter(document), None) != "schema" or document["schema"] != expected:
                findings.append(("PJ001", f"document [{file_name}] must start with schema [{expected}] found [{next(iter(document), None)}]"))
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
    model = manifest.get("model")
    findings.extend(("PJ003", f"file missing from manifest [{file_name}]") for file_name in (PROJECT_SIGNATURE, PROJECT_GOLDEN) if file_name not in files)
    if flavour in PROJECT_MODEL_FILES and (model != PROJECT_MODEL_FILES[flavour] or model not in files):
        findings.append(("PJ003", f"model file [{PROJECT_MODEL_FILES[flavour]}] missing from manifest model [{model}]"))
    for file_name, sha256 in files.items():
        file_path = join(project_dir, file_name)
        if not isfile(file_path):
            findings.append(("PJ003", f"file absent [{file_name}]"))
        elif file_sha256(file_path) != sha256:
            findings.append(("PJ003", f"file checksum mismatch [{file_name}]"))
    release_path = join(project_dir, PROJECT_RELEASE)
    if isfile(release_path):
        try:
            with open(release_path) as release_file:
                release = json.load(release_file)
        except ValueError:
            release = None
        if not isinstance(release, dict) or not isinstance(release.get("version"), str) or not isinstance(release.get("released_at"), str):
            findings.append(("PJ018", f"release file needs a version and a released_at as text [{PROJECT_RELEASE}]"))
        elif release.get("content_sha256") != file_sha256(join(project_dir, PROJECT_MANIFEST)):
            findings.append(("PJ018", f"release file differs from the project [{release.get('content_sha256')}]"))
    if flavour == "wasm" and model in files and isfile(join(project_dir, model)):
        import wasmtime

        f64 = wasmtime.ValType.f64()
        for entry in wasm_module_imports(join(project_dir, model)):
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
    if flavour == "pyfunc" or (flavour == "wasm" and model in files):
        kind = "python" if flavour == "pyfunc" else "wasm"
        listed = runtime.get(kind) if isinstance(runtime, dict) else None
        if not isinstance(listed, list) or not all(isinstance(name, str) for name in listed) or listed != sorted(set(listed)):
            findings.append(("PJ017", f"runtime [{kind}] must be a sorted list of unique names for flavour [{flavour}]"))
        else:
            findings.extend(("PJ017", f"runtime holds a key the flavour does not use [{key}]") for key in sorted(set(runtime) - {kind}))
            model_file = join(project_dir, model) if model in files else None
            if model_file is not None and isfile(model_file) and flavour == "wasm":
                actual = sorted({str(entry.name) for entry in wasm_module_imports(model_file)})
                if listed != actual:
                    findings.append(("PJ017", f"runtime wasm differs from the module imports runtime {listed} module {actual}"))
            elif model_file is not None and isfile(model_file):
                with open(model_file) as source_file:
                    needed = pyfunc_imports(source_file.read())
                declared = {PYFUNC_IMPORT_NAMES.get(re.sub(r"[-_.]+", "_", name.lower()), re.sub(r"[-_.]+", "_", name.lower())): name for name in listed}
                findings.extend(("PJ017", f"model imports a package that runtime python does not declare [{name}]") for name in sorted(needed - set(declared)))
                findings.extend(("PJ017", f"runtime python declares a package the model does not need [{declared[name]}]") for name in sorted(set(declared) - needed))
    elif runtime is not None:
        findings.append(("PJ017", f"flavour [{flavour}] takes no runtime"))
    if PROJECT_SIGNATURE not in files or not isfile(join(project_dir, PROJECT_SIGNATURE)):
        return findings
    with open(join(project_dir, PROJECT_SIGNATURE)) as signature_file:
        signature = json.load(signature_file)
    findings.extend(_lint_signature(manifest, signature))
    if PROJECT_EVALUATION in files:
        findings.extend(_lint_evaluation(project_dir, signature))
    elif flavour in PROJECT_FLAVOURS and flavour != "static":
        findings.append(("AC001", f"a project of flavour [{flavour}] needs an acceptance evaluation"))
    if PROJECT_GOLDEN in files and isfile(join(project_dir, PROJECT_GOLDEN)):
        with open(join(project_dir, PROJECT_GOLDEN)) as golden_file:
            golden = json.load(golden_file)
        findings.extend(_lint_golden(manifest, signature, golden))
    return findings


def verify_project(project_dir):
    findings = lint_project(project_dir)
    if findings:
        raise GateError("Package", "project", "; ".join(f"{rule} {message}" for rule, message in findings))
    with open(join(project_dir, PROJECT_MANIFEST)) as manifest_file:
        return json.load(manifest_file)


def fix_hints(rules):
    hints = []
    for rule in rules:
        hint = PROJECT_FIX_HINTS.get(rule) or PROJECT_FIX_HINTS.get(rule[:2])
        if hint and hint not in hints:
            hints.append(hint)
    return hints


def _lint_evaluation(project_dir, signature):
    evaluation_path = join(project_dir, PROJECT_EVALUATION)
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
        elif (entry.get("passed"), entry.get("budget")) != acceptance_outcome(value, limit, direction):
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
    if evaluation.get("passed") is not all(entry.get("passed") is True for entry in entries if entry.get("gate") is True) or evaluation.get("budget") != acceptance_budget(entries):
        findings.append(("AC003", "the evaluation verdict and budget do not match its checks"))
    if evaluation.get("independent") is not ("backtest" in datasets):
        findings.append(("AC005", "the evaluation must say it is independent exactly when a backtest dataset is recorded"))
    if "backtest" in datasets and any(entry.get("split") == "validation" and entry.get("gate") is True for entry in entries):
        findings.append(("AC005", "a validation check gates only when the evaluation holds no backtest"))
    findings.extend(_lint_folds(evaluation.get("folds"), {entry.get("name") for entry in entries if entry.get("gate") is True}))
    return findings


def _lint_folds(folds, gated):
    if folds is None:
        return []
    if not isinstance(folds, list) or not folds or not all(isinstance(entry, dict) for entry in folds):
        return [("AC004", "folds must be a non-empty list of records")]
    findings = []
    if [entry.get("fold") for entry in folds] != list(range(len(folds))):
        findings.append(("AC004", "folds must be numbered from 0 in order"))
    for entry in folds:
        label = f"fold [{entry.get('fold')}]"
        if entry.get("scheme") not in FOLD_SCHEMES:
            findings.append(("AC004", f"fold scheme is not one of {list(FOLD_SCHEMES)} {label}"))
        for key, minimum in (("gap", 0), ("training", 1), ("validation", 1)):
            value = entry.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                findings.append(("AC004", f"fold {key} must be an integer of at least {minimum} {label}"))
    metrics = [sorted(set(entry) - set(FOLD_KEYS)) for entry in folds]
    if any(names != metrics[0] for names in metrics):
        findings.append(("AC004", "every fold must record the same metrics"))
    for name in metrics[0]:
        if not all(isinstance(entry.get(name), (int, float)) and not isinstance(entry.get(name), bool) for entry in folds):
            findings.append(("AC004", f"fold metric [{name}] must be a number in every fold"))
        findings.extend(("AC004", f"fold metric [{name}] needs a gating check named [{gate}]") for gate in (f"{name}_mean", f"{name}_worst") if gate not in gated)
    return findings


def _lint_signature(manifest, signature):
    findings = []
    name = manifest.get("name", "")
    if not PROJECT_NAME.match(name):
        findings.append(("PJ004", f"name does not follow the naming style [{name}]"))
    if signature.get("name") != name:
        findings.append(("PJ004", f"signature name [{signature.get('name')}] differs from the project name [{name}]"))
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
    for entry in signature["outputs"]:
        unit = entry.get("parameters", {}).get("unit")
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


def pyfunc_imports(text):
    tree = ast.parse(text)
    imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported |= {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module}
    return imported - set(sys.stdlib_module_names) - set(PYFUNC_BASE_IMPORTS)


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def acceptance_outcome(value, limit, direction):
    if value is None:
        return False, None
    if direction == "max":
        return value <= limit, (max(value, 0) / limit if limit > 0 else (0.0 if value <= 0 else None))
    return value >= limit, (limit / value if value > 0 else None)


def acceptance_budget(checks):
    budgets = [entry.get("budget") for entry in checks if entry.get("gate") is True]
    return None if not budgets or any(budget is None for budget in budgets) else max(budgets)


def wasm_module_imports(path):
    import wasmtime

    with open(path, "rb") as model_file:
        return wasmtime.Module(wasmtime.Engine(), model_file.read()).imports
