import subprocess
import sys
from os.path import abspath, dirname, isfile, join, realpath

import pytest

sys.path.append("../../../main/python")
sys.path.append("../../../../../../all/_/src/build/python")

from asystem.report import run_pytest, stage
from workbench.config import VERSION_PATH
from workbench.errors import GateError
from workbench.metadata import METADATA_FILE, PROJECT_DIR, read_metadata, record_passed
from workbench.model import PROJECT_ALIAS_PREVIEW
from workbench.release import clear_preview, wait_served, workspaces

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
DIR_SOURCE = abspath(join(DIR_ROOT, "../.."))
TIMEOUT_RUN = 300


def _label(target):
    return target["kind"] if target["kind"] == "served" else f"embedded-{target['language']}"


def _targets():
    found = []
    for name, directory in workspaces(DIR_SOURCE).items():
        if isfile(join(directory, METADATA_FILE)):
            found.extend(pytest.param(name, directory, target, id=f"{name}-{_label(target)}") for target in read_metadata(directory)["targets"] if target["kind"] != "local")
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
    for name in sorted(registered):
        clear_preview(name, env["MLFLOW_TRACKING_URI"])


@pytest.mark.parametrize(("name", "directory", "target"), _targets())
def test_a_declared_target_runs_its_project(name, directory, target, env, image, previews):
    metadata = read_metadata(directory)
    project_dir = join(directory, PROJECT_DIR)
    if target["kind"] == "served":
        with stage("compile") as entry:
            entry.detail = "interpreted"
        previews.add(name)
        with stage("registry") as entry:
            _wait_registry(name, metadata["content_sha256"], env["MLFLOW_TRACKING_URI"])
            entry.detail = PROJECT_ALIAS_PREVIEW
        server = f"http://{env['MLSERVER_SERVICE_PROD']}:{env['MLSERVER_HTTP_PORT']}"
        with stage("serve") as entry:
            wait_served(server, f"{name}_preview", f"preview-{metadata['content_sha256'][:8]}")
            entry.detail = f"{name}_preview"
        output = _run(image, "python", ["-m", "consumer.main", "/project", server, f"{name}_preview"], project_dir)
    else:
        with stage("compile") as entry:
            entry.detail = "interpreted" if target["language"] == "python" else "prebuilt"
        output = _run(image, target["language"], ["-m", "consumer.main", "/project"] if target["language"] == "python" else ["/project"], project_dir)
    print(output.stdout, end="", flush=True)
    if output.returncode != 0:
        raise GateError("target", _label(target), f"workspace [{name}] output [{(output.stderr or output.stdout).strip()}]")
    record_passed(directory, target)


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
