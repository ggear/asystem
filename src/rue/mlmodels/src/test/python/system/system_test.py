import json
import subprocess
import sys
from os.path import abspath, dirname, isfile, join, realpath, relpath

import pytest

sys.path.append("../../../main/python")
sys.path.append("../../../../../../all/_/src/build/python")

from asystem.report import run_pytest, stage
from mlmodels._config import VERSION_PATH
from mlmodels._constants import PROJECT_ALIAS_PREVIEW, PROJECT_LABEL_PREVIEW, PROJECT_PREVIEW_SUFFIX, PROJECT_SIGNATURE
from mlmodels._errors import GateError
from mlmodels._metadata import METADATA_FILE, PROJECT_DIR, read_metadata
from mlmodels._registry import registry_client
from mlmodels._release import consumers, slot_name, slots, wait_served, workspaces
from mlmodels._signature import served_name

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
DIR_SOURCE = abspath(join(DIR_ROOT, "../.."))
TIMEOUT_RUN = 300


def _label(target):
    return target["kind"] if target["kind"] == "served" else f"embedded-{target['language']}"


def _targets():
    found = []
    for name, directory in workspaces(DIR_SOURCE).items():
        if isfile(join(directory, METADATA_FILE)):
            target = read_metadata(directory)["target"]
            if target["kind"] != "local":
                found.append(pytest.param(name, directory, target, id=f"{name}-{_label(target)}"))
    return found


@pytest.fixture(scope="session")
def env():
    values = {}
    with open(join(DIR_ROOT, ".env")) as env_file:
        for line in env_file:
            key, separator, value = line.rstrip().partition("=")
            if separator and not key.startswith("#"):
                values[key] = value.strip('"')
    return values


@pytest.fixture(scope="session")
def image():
    with open(VERSION_PATH) as version_file:
        tag = f"mlmodels:{version_file.read().strip()}"
    with stage("image") as entry:
        if subprocess.run(["docker", "image", "inspect", tag], capture_output=True, check=False).returncode != 0:
            raise GateError("image", "missing", f"image [{tag}] was not built, run fab test_sys, which packages it first")
        entry.detail = tag
    return tag


@pytest.fixture(scope="session")
def previews(env):
    registered = set()
    yield registered
    client = registry_client(env["MLFLOW_TRACKING_URI"])
    for name in sorted(registered):
        if PROJECT_ALIAS_PREVIEW in client.get_registered_model(name).aliases:
            client.delete_registered_model_alias(name, PROJECT_ALIAS_PREVIEW)


@pytest.mark.parametrize(("name", "directory", "target"), _targets())
def test_the_declared_target_runs_its_project(name, directory, target, env, image, previews):
    metadata = read_metadata(directory)
    project_dir = join(directory, PROJECT_DIR)
    if target["kind"] == "served":
        with stage("compile") as entry:
            entry.detail = "interpreted"
        with open(join(project_dir, PROJECT_SIGNATURE)) as signature_file:
            registered = served_name(name, json.load(signature_file))
        previews.add(registered)
        with stage("registry") as entry:
            _wait_registry(registered, metadata["content_sha256"], env["MLFLOW_TRACKING_URI"])
            entry.detail = PROJECT_ALIAS_PREVIEW
        server = f"http://{env['MLSERVER_SERVICE_PROD']}:{env['MLSERVER_HTTP_PORT']}"
        serving, label = (registered, metadata["version"]) if metadata["release"] is not None else (f"{registered}{PROJECT_PREVIEW_SUFFIX}", f"{PROJECT_LABEL_PREVIEW}{metadata['content_sha256'][:8]}")
        with stage("serve") as entry:
            wait_served(server, serving, label)
            entry.detail = serving
        output = _run(image, "python", ["-m", "mlmodels.runtime", "/project", server, serving], project_dir)
    else:
        with stage("compile") as entry:
            entry.detail = "interpreted" if target["language"] == "python" else "prebuilt"
        arguments = ["-m", "mlmodels.runtime", "/project"] if target["language"] == "python" else ["/project"]
        output = _run(image, target["language"], arguments, project_dir)
        for slot in [slot for consumer in consumers(DIR_SOURCE) for slot in slots(consumer) if slot_name(slot) == name]:
            with stage("embedded") as entry:
                entry.detail = relpath(slot, DIR_SOURCE)
            slot_output = _run(image, target["language"], arguments, slot)
            if slot_output.returncode != 0:
                raise GateError("target", _label(target), f"workspace [{name}] embedded copy [{relpath(slot, DIR_SOURCE)}] output [{(slot_output.stderr or slot_output.stdout).strip()}]")
    print(output.stdout, end="", flush=True)
    if output.returncode != 0:
        raise GateError("target", _label(target), f"workspace [{name}] output [{(output.stderr or output.stdout).strip()}]")


def _wait_registry(name, content_sha256, tracking_uri):
    import time

    from mlflow.exceptions import MlflowException

    import mlflow
    from mlflow import MlflowClient

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_registry_uri(tracking_uri)
    client = MlflowClient()
    deadline = time.monotonic() + TIMEOUT_RUN
    while time.monotonic() < deadline:
        try:
            if client.get_model_version_by_alias(name, PROJECT_ALIAS_PREVIEW).tags.get("content_sha256") == content_sha256:
                return
        except MlflowException:
            pass
        time.sleep(2)
    raise GateError("mlflow", "preview", f"model [{name}] alias [{PROJECT_ALIAS_PREVIEW}] with content [{content_sha256[:8]}] not visible within [{TIMEOUT_RUN}] seconds")


def _run(image, language, arguments, project_dir):
    command = ["python", *arguments] if language == "python" else [f"/asystem/bin/{language}", *arguments]
    return subprocess.run(["docker", "run", "--rm", "--volume", f"{project_dir}:/project:ro", image, *command], capture_output=True, text=True, timeout=TIMEOUT_RUN, check=False)


if __name__ == "__main__":
    sys.exit(run_pytest("mlmodels/systest", ["-s", "-o", f"cache_dir={join(DIR_ROOT, 'target/.pytest_cache')}", __file__]))
