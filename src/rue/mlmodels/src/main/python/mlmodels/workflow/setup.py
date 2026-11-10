import os.path

from mlmodels._config import ENV_PATH, NOTEBOOK_DIR
from mlmodels._log import configure_log
from mlmodels._signature import registered_name
from mlmodels._workspace import Workspace, describe_workspace, load_signature, read_env, scratch_project_dir, signature_names


def setup_workspace(workspace, notebook_dir=NOTEBOOK_DIR, env_path=ENV_PATH):
    configure_log()
    module, model, notebook = workspace.split("/")
    path = os.path.join(notebook_dir, workspace)
    signature = load_signature(workspace, notebook_dir)
    inputs, outputs = signature_names(signature)
    print(describe_workspace(path, signature))
    return Workspace(workspace, path, notebook_dir, registered_name(module, model, notebook), read_env(env_path), signature, inputs, outputs, scratch_project_dir(workspace))
