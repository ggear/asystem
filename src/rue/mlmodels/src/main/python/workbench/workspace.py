import argparse
import re
import sys
from os import listdir
from os.path import basename, dirname, isdir, join, splitext

from workbench.metadata import METADATA_FILE, PROJECT_DIR, REQUIREMENT_FILES, SIGNATURE_FILE
from workbench.model import PROJECT_MODEL_FILES, PROJECT_NAME, PROJECT_SPLITS

WORKSPACE_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$")
WORKSPACE_DATE_RANGE = re.compile(r"_\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}$")
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
    allowed = {WORKSPACE_NOTEBOOK, "plan.md", METADATA_FILE, SIGNATURE_FILE, PROJECT_DIR, "data", *REQUIREMENT_FILES.values(), *PROJECT_MODEL_FILES.values(), *WORKSPACE_IGNORED}
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
    for timestamp in sorted(listdir(split_dir)):
        if timestamp in WORKSPACE_IGNORED:
            continue
        path = join(split_dir, timestamp)
        if not isdir(path) or not WORKSPACE_TIMESTAMP.match(timestamp):
            findings.append(("WS005", f"[data/{split}/{timestamp}] is not a timestamp directory YYYY-MM-DD_HH-MM-SS"))
            continue
        for file_name in sorted(listdir(path)):
            name, extension = splitext(file_name)
            owned = name == f"{model}_{notebook}" or name.startswith(f"{model}_{notebook}_")
            if extension != ".csv" or not PROJECT_NAME.match(name.replace("-", "_")) or not owned:
                findings.append(("WS006", f"[data/{split}/{timestamp}/{file_name}] must be a csv named [{model}_{notebook}_<dimension>...]"))
            elif split != "golden" and not WORKSPACE_DATE_RANGE.search(name):
                findings.append(("WS006", f"[data/{split}/{timestamp}/{file_name}] must end with the first and last date it covers, _YYYY-MM-DD_YYYY-MM-DD"))
    return findings


def _names(directory, extension):
    return sorted(name for name in listdir(directory) if name.endswith(extension)) if isdir(directory) else []


if __name__ == "__main__":
    sys.exit(main())
