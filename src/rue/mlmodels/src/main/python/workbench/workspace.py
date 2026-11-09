import argparse
import hashlib
import json
import re
import sys
from os import listdir
from os.path import basename, dirname, isdir, isfile, join, splitext

from workbench.metadata import METADATA_FILE, PROJECT_DIR, REQUIREMENT_FILES, SIGNATURE_FILE
from workbench.model import PROJECT_MODEL_FILES, PROJECT_NAME, PROJECT_SPLITS

WORKSPACE_RUN = re.compile(r"^[1-9][0-9]*$")
WORKSPACE_IGNORED = (".gitkeep",)
WORKSPACE_NOTEBOOK = "notebook.ipynb"


def lint_workspace(notebook_dir):
    notebook_dir = notebook_dir.rstrip("/")
    notebook = basename(notebook_dir)
    model = basename(dirname(notebook_dir))
    module = basename(dirname(dirname(notebook_dir)))
    findings = []
    findings.extend(
        ("WS001", f"{level} directory [{name}] does not follow the naming style") for level, name in (("module", module), ("model", model), ("notebook", notebook)) if not PROJECT_NAME.match(name)
    )
    notebooks = _names(notebook_dir, ".ipynb")
    if notebooks != [WORKSPACE_NOTEBOOK]:
        findings.append(("WS002", f"the directory must hold exactly one notebook, [{WORKSPACE_NOTEBOOK}], found {notebooks}"))
    models = [name for name in PROJECT_MODEL_FILES.values() if isdir(notebook_dir) and name in listdir(notebook_dir)]
    if len(models) > 1:
        findings.append(("WS007", f"the directory must hold at most one model file, found {models}"))
    allowed = {WORKSPACE_NOTEBOOK, METADATA_FILE, SIGNATURE_FILE, PROJECT_DIR, "data", *REQUIREMENT_FILES.values(), *PROJECT_MODEL_FILES.values(), *WORKSPACE_IGNORED}
    if isdir(notebook_dir):
        findings.extend(("WS003", f"[{name}] is not one of {sorted(allowed)}") for name in sorted(listdir(notebook_dir)) if name not in allowed)
    data_dir = join(notebook_dir, "data")
    if isdir(data_dir):
        for split in sorted(listdir(data_dir)):
            if split not in PROJECT_SPLITS:
                findings.append(("WS004", f"[data/{split}] is not one of the splits {list(PROJECT_SPLITS)}"))
                continue
            findings.extend(_lint_split(model, notebook, join(data_dir, split), split))
    return findings


def main(arguments=None):
    parser = argparse.ArgumentParser(prog="workbench.workspace")
    parser.add_argument("paths", nargs="+")
    options = parser.parse_args(arguments)
    failed = False
    for path in options.paths:
        for rule, message in lint_workspace(path):
            failed = True
            print(f"{path} {rule} {message}", file=sys.stderr)
    return 1 if failed else 0


def _lint_split(model, notebook, split_dir, split):
    findings = []
    runs = sorted(entry for entry in listdir(split_dir) if entry not in WORKSPACE_IGNORED)
    for run in runs:
        path = join(split_dir, run)
        if not isdir(path) or not WORKSPACE_RUN.match(run):
            findings.append(("WS005", f"[data/{split}/{run}] is not a run directory numbered from 1"))
            continue
        for file_name in sorted(listdir(path)):
            name, extension = splitext(file_name)
            owned = name == f"{model}_{notebook}" or name.startswith(f"{model}_{notebook}_")
            if extension not in (".csv", ".json") or not PROJECT_NAME.match(name.replace("-", "_")) or not owned:
                findings.append(("WS006", f"[data/{split}/{run}/{file_name}] must be a csv and its json named [{model}_{notebook}_<dimension>...]"))
            elif extension == ".csv":
                findings.extend(_lint_sidecar(path, split, run, name))
            elif name + ".csv" not in listdir(path):
                findings.append(("WS008", f"[data/{split}/{run}/{file_name}] describes no csv"))
    numbers = sorted(int(run) for run in runs if WORKSPACE_RUN.match(run))
    if numbers != list(range(1, len(numbers) + 1)):
        findings.append(("WS005", f"[data/{split}] runs must be numbered from 1 without gaps found {numbers}"))
    return findings


def _lint_sidecar(path, split, run, name):
    sidecar = join(path, f"{name}.json")
    if not isfile(sidecar):
        return [("WS008", f"[data/{split}/{run}/{name}.json] is missing, the csv has no record of its source")]
    with open(sidecar) as sidecar_file:
        meta = json.load(sidecar_file)
    with open(join(path, f"{name}.csv"), "rb") as data_file:
        digest = hashlib.sha256(data_file.read()).hexdigest()
    expected = {"split": split, "run": int(run), "name": name, "sha256": digest}
    return [("WS008", f"[data/{split}/{run}/{name}.json] has {key} [{meta.get(key)}] and the csv gives [{value}]") for key, value in expected.items() if meta.get(key) != value]


def _names(directory, extension):
    return sorted(name for name in listdir(directory) if name.endswith(extension)) if isdir(directory) else []


if __name__ == "__main__":
    sys.exit(main())
