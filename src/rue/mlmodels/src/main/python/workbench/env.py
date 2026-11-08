import json
import os
import os.path

from workbench.config import MODULE_DIR
from workbench.metadata import METADATA_FILE, PROJECT_DIR, SIGNATURE_FILE, read_runtime


def init_env():
    env = _read_env(os.path.join(MODULE_DIR, ".env"))
    workspace_dir = os.getcwd()
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
    signature_path = os.path.join(workspace_dir, SIGNATURE_FILE)
    if os.path.isfile(signature_path):
        with open(signature_path) as signature_file:
            signature = json.load(signature_file)
        for kind in ("inputs", "outputs"):
            entries = [f"{entry['name']} [{entry['parameters']['unit']}]" for entry in signature[kind]]
            rows.extend((kind if index == 0 else "", entry) for index, entry in enumerate(entries or ["none"]))
    if rows:
        print("\n".join(f"{key:<10}{value}" for key, value in rows))
    return env


def _read_env(path):
    env = {}
    with open(path) as env_file:
        for env_line in env_file:
            env_line = env_line.replace("export ", "").rstrip()
            if not env_line.startswith("#") and "=" in env_line:
                env_key, env_value = env_line.split("=", 1)
                env[env_key] = env_value
    return env
