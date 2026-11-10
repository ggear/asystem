import json
import os.path
import shutil
import tempfile
from dataclasses import dataclass, field

from mlmodels._config import NOTEBOOK_DIR
from mlmodels._constants import MODEL_DIR, MODEL_DOCUMENT, PROJECT_SPLITS
from mlmodels._metadata import METADATA_FILE, SIGNATURE_FILE, read_runtime
from mlmodels._selection import Selection


def scratch_project_dir(workspace, output_dir=None):
    output_dir = output_dir if output_dir is not None else os.environ.get("MODEL_OUTPUT_DIR")
    if not output_dir:
        return os.path.join(tempfile.mkdtemp(), "project")
    project_dir = os.path.join(output_dir, "project", workspace)
    shutil.rmtree(project_dir, ignore_errors=True)
    return project_dir


def load_signature(workspace, notebook_dir=NOTEBOOK_DIR):
    with open(os.path.join(notebook_dir, workspace, SIGNATURE_FILE)) as signature_file:
        return json.load(signature_file)


def signature_names(signature):
    return [entry["name"] for entry in signature["inputs"]], [entry["name"] for entry in signature["outputs"]]


@dataclass
class Workspace:
    name: str
    path: str
    notebook_dir: str
    model_name: str
    env: dict
    signature: dict
    inputs: list
    outputs: list
    project_dir: str
    runs: dict = field(default_factory=dict)
    splits: dict = field(default_factory=dict)
    folds: list = field(default_factory=list)
    models: dict = field(default_factory=dict)
    params: dict = field(default_factory=dict)
    target: dict | None = None

    def run(self, run, name=None):
        name = name if name is not None else self.model_name.split("_", 1)[1]
        if (run, name) not in self.runs:
            raise KeyError(f"run [{run}] [{name}] was not collected, call collect_run first")
        return Selection(self, run, name, tuple(range(self.runs[(run, name)].frame.height)))

    def __setattr__(self, name, value):
        if name not in self.__dataclass_fields__:
            raise AttributeError(f"workspace has no field [{name}], pass data between stages in ws.params")
        object.__setattr__(self, name, value)

    def __getattr__(self, name):
        if name in PROJECT_SPLITS:
            if name not in self.__dict__["splits"]:
                raise AttributeError(f"split [{name}] is not defined, call prepare_split first")
            return self.__dict__["splits"][name].frame
        raise AttributeError(name)


def describe_workspace(workspace_dir, signature):
    rows = []
    metadata_path = os.path.join(workspace_dir, METADATA_FILE)
    if os.path.isfile(metadata_path):
        with open(metadata_path) as metadata_file:
            metadata = json.load(metadata_file)
        runtime = ", ".join(f"{kind} {' '.join(names)}" for kind, names in read_runtime(workspace_dir).items() if names)
        rows = [
            ("Workspace", "/".join(workspace_dir.rstrip("/").split("/")[-3:])),
            ("Target", " ".join(metadata["target"][key] for key in ("kind", "language") if key in metadata["target"])),
            ("Runtime", runtime or "none"),
            ("Version", f"{metadata['version']} ({'released' if metadata['release'] else 'unreleased'})" if metadata["version"] else "none"),
        ]
    for kind in ("inputs", "outputs"):
        entries = [f"{entry['name']} [{entry['parameters']['unit']}]" for entry in signature[kind]]
        rows.extend((kind.capitalize() if index == 0 else "", entry) for index, entry in enumerate(entries or ["none"]))
    rows.extend(describe_runs(workspace_dir))
    rows.extend(describe_models(workspace_dir))
    return "\n".join(f"{key:<10}{value}" for key, value in rows)


def describe_runs(workspace_dir):
    data_dir = os.path.join(workspace_dir, "data")
    rows = []
    for run in sorted(int(entry) for entry in os.listdir(data_dir) if entry.isdigit()) if os.path.isdir(data_dir) else []:
        run_dir = os.path.join(data_dir, str(run))
        for file_name in sorted(entry for entry in os.listdir(run_dir) if entry.endswith(".json")):
            with open(os.path.join(run_dir, file_name)) as sidecar_file:
                meta = json.load(sidecar_file)
            rows.append(("Data" if not rows else "", f"{run} [{meta.get('label', '')}] with rows [{meta['rows']}]"))
    return rows


def read_env(path):
    env = {}
    with open(path) as env_file:
        for env_line in env_file:
            env_line = env_line.replace("export ", "").rstrip()
            if not env_line.startswith("#") and "=" in env_line:
                env_key, env_value = env_line.split("=", 1)
                env[env_key] = env_value
    return env


def describe_models(workspace_dir):
    model_dir = os.path.join(workspace_dir, MODEL_DIR)
    rows = []
    for model in sorted(int(entry) for entry in os.listdir(model_dir) if entry.isdigit()) if os.path.isdir(model_dir) else []:
        with open(os.path.join(model_dir, str(model), MODEL_DOCUMENT)) as document_file:
            document = json.load(document_file)
        rows.append(("Models" if not rows else "", f"{model} [{document['label']}] as [{document['flavour']}]"))
    return rows
