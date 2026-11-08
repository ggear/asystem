import json
import os.path
import shutil
import tempfile

from workbench.config import NOTEBOOK_DIR, PINS_PATH, VERSION_PATH
from workbench.metadata import SIGNATURE_FILE
from workbench.metadata import record_project as record_workspace_project


def scratch_project_dir(workspace, output_dir=None):
    output_dir = output_dir if output_dir is not None else os.environ.get("MODEL_OUTPUT_DIR")
    if not output_dir:
        return os.path.join(tempfile.mkdtemp(), "project")
    project_dir = os.path.join(output_dir, "project", workspace)
    shutil.rmtree(project_dir, ignore_errors=True)
    return project_dir


def provenance(source, trained_on, paths, notes="", implementation=None, notebook_dir=NOTEBOOK_DIR):
    document = {"source": source, "trained_on": trained_on, "inputs": [os.path.relpath(path, notebook_dir) for path in paths], "notes": notes}
    if implementation is not None:
        document["implementation"] = implementation
    return document


def record_project(workspace, project_dir, target, notebook_dir=NOTEBOOK_DIR, pins_path=PINS_PATH, version_path=VERSION_PATH):
    return record_workspace_project(os.path.join(notebook_dir, workspace), project_dir, target, pins_path, version_path)


def load_signature(workspace, notebook_dir=NOTEBOOK_DIR):
    with open(os.path.join(notebook_dir, workspace, SIGNATURE_FILE)) as signature_file:
        return json.load(signature_file)


def signature_names(signature):
    return [entry["name"] for entry in signature["inputs"]], [entry["name"] for entry in signature["outputs"]]
