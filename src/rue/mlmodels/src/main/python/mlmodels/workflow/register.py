import json
import logging
from os.path import join

from mlmodels._constants import PROJECT_MANIFEST
from mlmodels._errors import GateError
from mlmodels._metadata import read_metadata
from mlmodels._registry import register_preview

LOG = logging.getLogger(__name__)


def register_model(ws, model):
    with open(join(ws.project_dir, PROJECT_MANIFEST)) as manifest_file:
        packaged = json.load(manifest_file).get("model_id")
    if packaged != model:
        raise GateError("Register", "model", f"model [{model}] is not the packaged model [{packaged}]")
    metadata = read_metadata(ws.path)
    version = register_preview(ws.project_dir, ws.model_name, ws.env["MLFLOW_TRACKING_URI"], metadata["target"], metadata["version"])
    if version is None:
        LOG.info("Register model [%s] not registered as the target is not served", model)
    else:
        LOG.info("Register model [%s] [%s] as version [%s] with alias [preview]", model, ws.models[model].label, version)
        LOG.info("Register model [%s] at [%s/#/models/%s/versions/%s]", model, ws.env["MLFLOW_TRACKING_URI"], ws.model_name, version)
        LOG.info("Register model [%s] release is set by hand after review", model)
