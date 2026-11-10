import logging
import os.path
import sys

from mlmodels._config import ENV_PATH, NOTEBOOK_DIR
from mlmodels._signature import registered_name
from mlmodels._workspace import Workspace, describe_workspace, load_signature, read_env, scratch_project_dir, signature_names


class LogFormatter(logging.Formatter):
    def format(self, record):
        message = super().format(record)
        return message if record.levelno == logging.INFO else f"{record.levelname} {message}"


def setup_workspace(workspace, notebook_dir=NOTEBOOK_DIR, env_path=ENV_PATH):
    log = logging.getLogger("mlmodels")
    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(LogFormatter("%(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False
    module, model, notebook = workspace.split("/")
    path = os.path.join(notebook_dir, workspace)
    signature = load_signature(workspace, notebook_dir)
    inputs, outputs = signature_names(signature)
    print(describe_workspace(path, signature))
    return Workspace(workspace, path, notebook_dir, registered_name(module, model, notebook), read_env(env_path), signature, inputs, outputs, scratch_project_dir(workspace))
