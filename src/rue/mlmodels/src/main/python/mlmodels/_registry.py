import json
import os
import shutil
import tempfile
from os.path import dirname, join

from mlmodels._constants import (
    PROJECT_ALIAS_PREVIEW,
    PROJECT_EVALUATION,
    PROJECT_GOLDEN,
    PROJECT_MANIFEST,
    PROJECT_SIGNATURE,
    PROJECT_TAG_CONTENT_SHA256,
    PROJECT_TAG_FLAVOUR,
    PROJECT_TAG_RELEASE_VERSION,
)
from mlmodels._lint_project import verify_project
from mlmodels._metadata import content_sha256
from mlmodels._project import check_acceptance
from mlmodels._tracking import log_tracking, project_tracking, source_tags


def register_project(project_dir, name, tracking_uri, aliases=(PROJECT_ALIAS_PREVIEW,), snapshot_version=None, tracking=None):
    import mlflow.pyfunc

    import mlflow

    manifest = verify_project(project_dir)
    client = registry_client(tracking_uri)
    content = content_sha256(project_dir)
    version = next((candidate for candidate in client.search_model_versions(f"name = '{name}'") if candidate.tags.get(PROJECT_TAG_CONTENT_SHA256) == content), None)
    if version is None:
        experiment = client.get_experiment_by_name(name)
        if experiment is None and tracking_uri.startswith("sqlite:///"):
            client.create_experiment(name, artifact_location="file://" + join(dirname(os.path.abspath(tracking_uri.removeprefix("sqlite:///"))), "artifacts"))
        elif experiment is not None and experiment.lifecycle_stage == "deleted":
            client.restore_experiment(experiment.experiment_id)
        mlflow.set_experiment(name)
        pyfunc_uri = ""
        with mlflow.start_run(tags={"mlflow.source.name": "mlmodels", **source_tags(project_dir)}) as run:
            mlflow.set_tags({PROJECT_TAG_FLAVOUR: manifest["flavour"]})
            if PROJECT_EVALUATION in manifest["files"]:
                with open(join(project_dir, PROJECT_EVALUATION)) as evaluation_file:
                    evaluation = json.load(evaluation_file)
                mlflow.set_tags({"acceptance": "passed" if evaluation["passed"] else "failed", "acceptance_budget": str(evaluation["budget"])})
                mlflow.log_metrics({"acceptance_passed": float(evaluation["passed"]), **({"acceptance_budget": evaluation["budget"]} if evaluation["budget"] is not None else {})})
                mlflow.log_metrics({f"{entry['split']}/{entry['output']}/{entry['name']}": entry["value"] for entry in evaluation["checks"] if entry["value"] is not None})
            tracking = tracking if tracking is not None else project_tracking(project_dir, manifest)
            log_tracking(tracking)
            if manifest["flavour"] == "pyfunc":
                import pandas
                from mlflow.models import ModelSignature
                from mlflow.types import ColSpec, Schema

                with open(join(project_dir, PROJECT_SIGNATURE)) as signature_file:
                    signature = json.load(signature_file)
                column_types = {"FP64": "double", "INT64": "long"}
                with open(join(project_dir, PROJECT_GOLDEN)) as golden_file:
                    golden = json.load(golden_file)
                first_step = next(step for sequence in golden["sequences"] for step in sequence["steps"] if "error" not in step)

                def schema(entries):
                    for entry in entries:
                        if entry["datatype"] not in column_types or entry["shape"] != [1]:
                            raise ValueError(f"pyfunc signature supports scalar FP64 and INT64 only [{entry['name']}]")
                    return Schema([ColSpec(column_types[entry["datatype"]], entry["name"], required=entry["parameters"]["required"]) for entry in entries])

                pyfunc_uri = mlflow.pyfunc.log_model(
                    name="project",
                    python_model=join(project_dir, manifest["model"]),
                    artifacts={"project": project_dir},
                    signature=ModelSignature(inputs=schema(signature["inputs"]), outputs=schema(signature["outputs"])),
                    input_example=pandas.DataFrame({entry["name"]: entry["data"] for entry in first_step["request"]["inputs"]}),
                ).model_uri
            else:
                mlflow.log_artifacts(project_dir, artifact_path="project")
        if manifest["flavour"] == "pyfunc":
            version = mlflow.register_model(pyfunc_uri, name)
        else:
            if not client.search_registered_models(filter_string=f"name = '{name}'"):
                client.create_registered_model(name)
            version = client.create_model_version(name, f"{run.info.artifact_uri}/project", run_id=run.info.run_id)
        for key, value in {PROJECT_TAG_CONTENT_SHA256: content, PROJECT_TAG_FLAVOUR: manifest["flavour"]}.items():
            client.set_model_version_tag(name, version.version, key, value)
        client.update_model_version(name, version.version, description=tracking["description"])
    if snapshot_version is not None and "snapshot_version" not in version.tags and PROJECT_TAG_RELEASE_VERSION not in version.tags:
        client.set_model_version_tag(name, version.version, "snapshot_version", snapshot_version)
    for alias in aliases:
        client.set_registered_model_alias(name, alias, version.version)
    return version.version


def register_preview(project_dir, name, tracking_uri, target, snapshot_version=None, tracking=None):
    if target["kind"] != "served":
        return None
    return register_project(project_dir, name, tracking_uri, aliases=(PROJECT_ALIAS_PREVIEW,), snapshot_version=snapshot_version, tracking=tracking)


def registry_client(tracking_uri):
    import mlflow
    from mlflow import MlflowClient

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(tracking_uri)
    return MlflowClient()


def registry_address(uri):
    from urllib.parse import urlparse

    if not uri:
        raise ValueError("MLFLOW_TRACKING_URI is not set")
    if urlparse(uri).port is not None:
        raise ValueError(f"registry address [{uri}] names a published port, use the proxy name, since the published port refuses every call but /health with an invalid host header")
    return uri


def check_release(project_dir):
    verify_project(project_dir)
    return check_acceptance(project_dir)


def registry_pull(name, alias, dest_dir, tracking_uri):
    from mlflow.artifacts import download_artifacts
    from mlflow.exceptions import MlflowException

    client = registry_client(tracking_uri)
    staging_dir = tempfile.mkdtemp(prefix=f"{name}-")
    try:
        try:
            tags = client.get_model_version_by_alias(name, alias).tags
            download_artifacts(artifact_uri=f"models:/{name}@{alias}", dst_path=staging_dir)
        except MlflowException as error:
            if error.error_code == "RESOURCE_DOES_NOT_EXIST" or "not found" in str(error.message):
                return None
            raise
        project_dir = next((current for current, _, names in os.walk(staging_dir) if PROJECT_MANIFEST in names), None)
        if project_dir is None:
            raise ValueError(f"no project found under [{staging_dir}]")
        manifest = verify_project(project_dir)
        if tags.get(PROJECT_TAG_CONTENT_SHA256) != content_sha256(project_dir):
            raise ValueError(f"pulled project differs from the registered content hash [{tags.get(PROJECT_TAG_CONTENT_SHA256)}]")
        shutil.rmtree(dest_dir, ignore_errors=True)
        shutil.copytree(project_dir, dest_dir)
        return manifest
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)
