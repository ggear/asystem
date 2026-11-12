import json
import tempfile
from os.path import join

from mlmodels._constants import PROJECT_MANIFEST
from mlmodels._errors import GateError
from mlmodels._metadata import read_metadata
from mlmodels._registry import registry_pull
from mlmodels._signature import served_name


def pull_model(ws, model):
    if read_metadata(ws.path)["target"]["kind"] != "served":
        print("Not pulled, the target is not served")
        return None
    pulled = registry_pull(served_name(ws.model_name, ws.signature), "preview", join(tempfile.mkdtemp(), "pulled"), ws.env["MLFLOW_TRACKING_URI"])
    if pulled is None:
        raise GateError("Pull", "registry", f"model [{model}] has no preview in the registry")
    with open(join(ws.project_dir, PROJECT_MANIFEST)) as manifest_file:
        local = json.load(manifest_file)
    if pulled.get("model_id") != model or pulled["files"] != local["files"]:
        raise GateError("Pull", "content", f"the registry preview differs from the project of model [{model}]")
    print(f"Pulled model [{model}] files [{len(pulled['files'])}] identical to the project")
    return pulled
