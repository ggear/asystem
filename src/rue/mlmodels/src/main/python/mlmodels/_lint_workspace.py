import json
from os import listdir
from os.path import abspath, basename, dirname, isdir, isfile, join, normpath, splitext

from mlmodels._constants import MODEL_DIR, MODEL_DOCUMENT, PROJECT_MODEL_FILES, PROJECT_NAME, PROJECT_SIGNATURE, RUN_FIRST
from mlmodels._lint_project import file_sha256
from mlmodels._metadata import METADATA_FILE, PROJECT_DIR, REQUIREMENT_FILES, read_metadata

WORKSPACE_IGNORED = (".gitkeep",)


WORKSPACE_NOTEBOOK = "notebook.ipynb"


WORKSPACE_EXAMPLE_MODULE = "example"


def lint_workspace(notebook_dir, source_dir=None):
    notebook_dir = notebook_dir.rstrip("/")
    notebook = basename(notebook_dir)
    model = basename(dirname(notebook_dir))
    module = basename(dirname(dirname(notebook_dir)))
    findings = []
    findings.extend(
        ("WS001", f"{level} directory [{name}] does not follow the naming style") for level, name in (("module", module), ("model", model), ("notebook", notebook)) if not PROJECT_NAME.match(name)
    )
    notebooks = sorted(name for name in listdir(notebook_dir) if name.endswith(".ipynb")) if isdir(notebook_dir) else []
    if notebooks != [WORKSPACE_NOTEBOOK]:
        findings.append(("WS002", f"the directory must hold exactly one notebook, [{WORKSPACE_NOTEBOOK}], found {notebooks}"))
    allowed = {WORKSPACE_NOTEBOOK, METADATA_FILE, PROJECT_SIGNATURE, PROJECT_DIR, "data", MODEL_DIR, *REQUIREMENT_FILES.values(), *WORKSPACE_IGNORED}
    if isdir(notebook_dir):
        findings.extend(("WS003", f"[{name}] is not one of {sorted(allowed)}") for name in sorted(listdir(notebook_dir)) if name not in allowed)
    data_dir = join(notebook_dir, "data")
    if isdir(data_dir):
        findings.extend(_lint_runs(model, notebook, data_dir))
    if isdir(join(notebook_dir, MODEL_DIR)):
        findings.extend(_lint_models(join(notebook_dir, MODEL_DIR)))
        findings.extend(_lint_columns(notebook_dir))
    if module != WORKSPACE_EXAMPLE_MODULE and isfile(join(notebook_dir, METADATA_FILE)) and read_metadata(notebook_dir)["target"]["kind"] == "embedded":
        source_dir = source_dir or normpath(join(abspath(notebook_dir), *[".."] * 8))
        if not any(isdir(join(source_dir, host, module)) for host in sorted(listdir(source_dir)) if isdir(join(source_dir, host))):
            findings.append(("WS014", f"an embedded workspace needs a module [{module}] under [{source_dir}] to embed it"))
    language = _loader_language(notebook_dir)
    if language is not None:
        module_dir = dirname(dirname(notebook_dir))
        findings.extend(
            ("WS013", f"notebook [{notebook}] is also in [{model_name}] and both load in [{language}]")
            for model_name in sorted(listdir(module_dir))
            if model_name != model and _loader_language(join(module_dir, model_name, notebook)) == language
        )
    return findings


def _is_number(entry):
    return entry.isdigit() and entry[0] != "0" and int(entry) >= RUN_FIRST


def _loader_language(notebook_dir):
    if not isfile(join(notebook_dir, METADATA_FILE)):
        return None
    target = read_metadata(notebook_dir)["target"]
    return {"served": "python", "embedded": target.get("language")}.get(target["kind"])


def _lint_runs(model, notebook, data_dir):
    findings = []
    runs = sorted(entry for entry in listdir(data_dir) if entry not in WORKSPACE_IGNORED)
    for run in runs:
        path = join(data_dir, run)
        if not isdir(path) or not _is_number(run):
            findings.append(("WS005", f"[data/{run}] is not a run directory numbered from [{RUN_FIRST}]"))
            continue
        for file_name in sorted(listdir(path)):
            name, extension = splitext(file_name)
            owned = name == f"{model}_{notebook}" or name.startswith(f"{model}_{notebook}_")
            if extension not in (".csv", ".json") or not PROJECT_NAME.match(name.replace("-", "_")) or not owned:
                findings.append(("WS006", f"[data/{run}/{file_name}] must be a csv and its json named [{model}_{notebook}_<dimension>...]"))
            elif extension == ".csv":
                findings.extend(_lint_sidecar(path, run, name))
            elif name + ".csv" not in listdir(path):
                findings.append(("WS008", f"[data/{run}/{file_name}] describes no csv"))
    headers = {}
    for run in runs:
        path = join(data_dir, run)
        if isdir(path) and _is_number(run):
            for file_name in listdir(path):
                if file_name.endswith(".csv"):
                    with open(join(path, file_name)) as data_file:
                        headers.setdefault(file_name, {}).setdefault(data_file.readline().strip(), []).append(run)
    findings.extend(
        ("WS009", f"[{name}] has different columns in runs {sorted(sum(by_header.values(), []))}, rewrite the older runs to the latest schema")
        for name, by_header in sorted(headers.items())
        if len(by_header) > 1
    )
    return findings


def _lint_models(model_dir):
    findings = []
    for entry in sorted(listdir(model_dir)):
        path = join(model_dir, entry)
        if entry in WORKSPACE_IGNORED:
            continue
        if not isdir(path) or not _is_number(entry):
            findings.append(("WS011", f"[model/{entry}] is not a model directory numbered from [{RUN_FIRST}]"))
            continue
        document_path = join(path, MODEL_DOCUMENT)
        if not isfile(document_path):
            findings.append(("WS011", f"[model/{entry}] has no [{MODEL_DOCUMENT}]"))
            continue
        with open(document_path) as document_file:
            document = json.load(document_file)
        if document.get("model") != int(entry):
            findings.append(("WS011", f"[model/{entry}/{MODEL_DOCUMENT}] has model [{document.get('model')}]"))
        files = [name for name in listdir(path) if name != MODEL_DOCUMENT]
        if document.get("flavour") == "static":
            if files:
                findings.append(("WS011", f"[model/{entry}] holds files {files} and a static model holds none"))
        elif files != [PROJECT_MODEL_FILES.get(document.get("flavour"))]:
            findings.append(("WS011", f"[model/{entry}] must hold only the model file of flavour [{document.get('flavour')}] found {files}"))
        elif file_sha256(join(path, files[0])) != document.get("sha256"):
            findings.append(("WS011", f"[model/{entry}/{files[0]}] differs from the sha256 in [{MODEL_DOCUMENT}]"))
    return findings


def _lint_columns(notebook_dir):
    models = []
    for entry in listdir(join(notebook_dir, MODEL_DIR)):
        document_path = join(notebook_dir, MODEL_DIR, entry, MODEL_DOCUMENT)
        if isfile(document_path):
            with open(document_path) as document_file:
                models.append(json.load(document_file).get("flavour"))
    signature_path = join(notebook_dir, PROJECT_SIGNATURE)
    data_dir = join(notebook_dir, "data")
    if not models or all(flavour == "static" for flavour in models) or not isfile(signature_path) or not isdir(data_dir):
        return []
    with open(signature_path) as signature_file:
        signature = json.load(signature_file)
    required = [entry["name"] for entry in signature["inputs"] if entry["parameters"]["required"]]
    findings = []
    for run in sorted(entry for entry in listdir(data_dir) if _is_number(entry)):
        for file_name in sorted(name for name in listdir(join(data_dir, run)) if name.endswith(".csv")):
            with open(join(data_dir, run, file_name)) as data_file:
                header = data_file.readline().strip().split(",")
            findings.extend(("WS012", f"[data/{run}/{file_name}] has no column for the required input [{name}]") for name in required if name not in header)
    return findings


def _lint_sidecar(path, run, name):
    sidecar = join(path, f"{name}.json")
    if not isfile(sidecar):
        return [("WS008", f"[data/{run}/{name}.json] is missing, the csv has no record of its source")]
    with open(sidecar) as sidecar_file:
        meta = json.load(sidecar_file)
    expected = {"run": int(run), "name": name, "sha256": file_sha256(join(path, f"{name}.csv"))}
    findings = [("WS008", f"[data/{run}/{name}.json] has {key} [{meta.get(key)}] and the csv gives [{value}]") for key, value in expected.items() if meta.get(key) != value]
    if not isinstance(meta.get("label"), str) or not meta["label"].strip():
        findings.append(("WS008", f"[data/{run}/{name}.json] has no label"))
    if not isinstance(meta.get("live"), bool):
        findings.append(("WS008", f"[data/{run}/{name}.json] has no live flag"))
    with open(join(path, f"{name}.csv")) as data_file:
        header = data_file.readline().strip().split(",")
    findings.extend(("WS010", f"[data/{run}/{name}.json] says [{column}] is inferred and the csv has no such column") for column in meta.get("inferred", []) if column not in header)
    return findings
