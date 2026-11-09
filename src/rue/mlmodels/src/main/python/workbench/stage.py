import json
import logging
import os
import os.path
import sys
from dataclasses import dataclass

import polars as pl

from workbench.config import ENV_PATH, NOTEBOOK_DIR
from workbench.metadata import METADATA_FILE, PROJECT_DIR, read_metadata, read_runtime
from workbench.model import package_project, register_preview, registered_name
from workbench.project import load_signature, provenance, record_project, scratch_project_dir, signature_names
from workbench.replay import require_replay


@dataclass
class Workspace:
    name: str
    path: str
    notebook_dir: str
    model_name: str
    target: dict
    env: dict
    signature: dict
    inputs: list
    outputs: list
    project_dir: str


def setup_workspace(workspace, target, notebook_dir=NOTEBOOK_DIR, env_path=ENV_PATH):
    log = logging.getLogger("workbench")
    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False
    module, model, notebook = workspace.split("/")
    path = os.path.join(notebook_dir, workspace)
    signature = load_signature(workspace, notebook_dir)
    inputs, outputs = signature_names(signature)
    print(_describe(path, signature))
    return Workspace(workspace, path, notebook_dir, registered_name(module, model, notebook), target, _read_env(env_path), signature, inputs, outputs, scratch_project_dir(workspace))


def package_workspace(
    ws,
    flavour,
    golden,
    *,
    trained_on,
    inputs=(),
    notes="",
    source="manual",
    implementation=None,
    model_path=None,
    evaluation=None,
    tolerance=None,
    sequence="golden",
    constants=None,
    python_deps=None,
):
    manifest = package_project(
        ws.project_dir,
        ws.model_name,
        flavour,
        ws.signature,
        pl.DataFrame(golden).iter_rows(named=True),
        provenance(source, trained_on, inputs, notes, implementation, ws.notebook_dir),
        constants=constants,
        model_path=model_path,
        sequence=sequence,
        evaluation=evaluation,
        tolerance=tolerance,
        python_deps=python_deps,
    )
    require_replay(ws.project_dir)
    record_project(ws.name, ws.project_dir, ws.target, ws.notebook_dir)
    print(manifest["name"], manifest["flavour"], "written to", ws.project_dir)
    print("replayed the golden sequences exactly through the shipped runtime")
    return manifest


def register_workspace(ws):
    version = register_preview(ws.project_dir, ws.model_name, ws.env["MLFLOW_TRACKING_URI"], ws.target, read_metadata(ws.path)["version"])
    print("not registered, the target is not served" if version is None else f"registered version {version} with alias preview, set release by hand after review")
    return version


def _describe(workspace_dir, signature):
    rows = []
    metadata_path = os.path.join(workspace_dir, METADATA_FILE)
    if os.path.isfile(metadata_path):
        with open(metadata_path) as metadata_file:
            metadata = json.load(metadata_file)
        manifest_path = os.path.join(workspace_dir, PROJECT_DIR, "project.json")
        flavour = "not packaged"
        if os.path.isfile(manifest_path):
            with open(manifest_path) as manifest_file:
                flavour = json.load(manifest_file)["flavour"]
        runtime = ", ".join(f"{kind} {' '.join(names)}" for kind, names in read_runtime(workspace_dir).items() if names)
        rows = [
            ("workspace", "/".join(workspace_dir.rstrip("/").split("/")[-3:])),
            ("flavour", flavour),
            ("target", " ".join(metadata["target"][key] for key in ("kind", "language") if key in metadata["target"])),
            ("runtime", runtime or "none"),
            ("version", f"{metadata['version']} ({'released' if metadata['release'] else 'unreleased'})" if metadata["version"] else "none"),
        ]
    for kind in ("inputs", "outputs"):
        entries = [f"{entry['name']} [{entry['parameters']['unit']}]" for entry in signature[kind]]
        rows.extend((kind if index == 0 else "", entry) for index, entry in enumerate(entries or ["none"]))
    return "\n".join(f"{key:<10}{value}" for key, value in rows)


def _read_env(path):
    env = {}
    with open(path) as env_file:
        for env_line in env_file:
            env_line = env_line.replace("export ", "").rstrip()
            if not env_line.startswith("#") and "=" in env_line:
                env_key, env_value = env_line.split("=", 1)
                env[env_key] = env_value
    return env
