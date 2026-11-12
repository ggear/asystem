import json
import logging
from os.path import join

from mlmodels._constants import PROJECT_MANIFEST
from mlmodels._errors import GateError
from mlmodels._metadata import read_metadata
from mlmodels._registry import register_preview
from mlmodels._signature import served_name
from mlmodels._tracking import tracking_context

LOG = logging.getLogger(__name__)


def register_model(ws, model):
    with open(join(ws.project_dir, PROJECT_MANIFEST)) as manifest_file:
        packaged = json.load(manifest_file).get("model_id")
    if packaged != model:
        raise GateError("Register", "model", f"model [{model}] is not the packaged model [{packaged}]")
    metadata = read_metadata(ws.path)
    registered = served_name(ws.model_name, ws.signature)
    version = register_preview(ws.project_dir, registered, ws.env["MLFLOW_TRACKING_URI"], metadata["target"], metadata["version"], tracking_context(ws, ws.models[model]), experiment=ws.model_name)
    if version is None:
        LOG.info("Register model [%s] not registered as the target is not served", model)
    else:
        LOG.info("Register model [%s] [%s] as version [%s] with alias [preview]", model, ws.models[model].label, version)
        LOG.info("Register model [%s] at [%s/#/models/%s/versions/%s]", model, ws.env["MLFLOW_TRACKING_URI"], registered, version)
        LOG.info("Register model [%s] release is set by hand after review", model)
