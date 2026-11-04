import json
import os
import shutil
import sys
import tempfile
from os.path import isdir, join

from serving.project import load_project

ALIAS = "release"
RUNTIME = "serving.runtime.ProjectRuntime"
SERVER_SETTINGS = {"host": "0.0.0.0", "http_port": 8080, "grpc_port": 8081, "parallel_workers": 0}


def main():
    tracking_uri = os.environ["MLFLOW_TRACKING_URI"]
    models_dir = os.environ["MLFLOW_MODEL_DIR"]
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "60")
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "2")
    from mlflow.artifacts import download_artifacts
    from mlflow.exceptions import MlflowException

    import mlflow
    from mlflow import MlflowClient

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(tracking_uri)
    listed = [name for name in os.environ.get("MLSERVER_MODELS", "").replace(",", " ").split() if name]
    names = listed or sorted(model.name for model in MlflowClient().search_registered_models() if ALIAS in model.aliases)
    os.makedirs(models_dir, exist_ok=True)
    for entry in os.listdir(models_dir):
        if isdir(join(models_dir, entry)) and entry not in names:
            shutil.rmtree(join(models_dir, entry))
            print(f"Removed model [{entry}] no longer declared")
    for name in names:
        staging_dir = tempfile.mkdtemp(prefix=f"{name}-", dir=models_dir)
        try:
            try:
                download_artifacts(artifact_uri=f"models:/{name}@{ALIAS}", dst_path=staging_dir)
                project_dir = next((root for root, _, files in os.walk(staging_dir) if "project.json" in files), None)
                if project_dir is None:
                    raise ValueError("no project in the pulled model")
                project = load_project(project_dir)
            except (OSError, ValueError, MlflowException) as error:
                print(f"ERROR Pull failed model [{name}] alias [{ALIAS}] [{error}]", file=sys.stderr)
                return 1
            settings = {
                "name": project.name,
                "implementation": RUNTIME,
                "parameters": {"version": project.version},
                "inputs": [{key: entry[key] for key in ("name", "datatype", "shape")} for entry in project.signature["inputs"]],
                "outputs": [{key: entry[key] for key in ("name", "datatype", "shape")} for entry in project.signature["outputs"]],
            }
            with open(join(project_dir, "model-settings.json"), "w") as settings_file:
                json.dump(settings, settings_file, indent=2, sort_keys=True)
            target_dir = join(models_dir, name)
            shutil.rmtree(target_dir, ignore_errors=True)
            os.rename(project_dir, target_dir)
            print(f"Pulled model [{name}] alias [{ALIAS}] version [{project.version}]")
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)
    with open(join(models_dir, "settings.json"), "w") as settings_file:
        json.dump(SERVER_SETTINGS, settings_file, indent=2, sort_keys=True)
    print(f"Serving [{len(names)}] models")
    return 0


if __name__ == "__main__":
    sys.exit(main())
