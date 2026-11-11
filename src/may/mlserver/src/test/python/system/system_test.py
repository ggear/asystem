import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from os.path import abspath, dirname, join, realpath

import pytest

sys.path.append("../../../../../../rue/mlmodels/src/main/python")

from mlmodels._registry import register_project
from mlmodels.testing import example_project

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
TIMEOUT_WARMUP = 300
TIMEOUT_POLL = 90
BOOTSTRAP = "mlserver_bootstrap"
NAME = "demo_replay_double"


@pytest.fixture(scope="module", autouse=True)
def bootstrapped():
    waited = subprocess.run(["docker", "wait", BOOTSTRAP], capture_output=True, text=True, timeout=TIMEOUT_WARMUP, check=False)
    assert waited.stdout.strip() == "0", f"{BOOTSTRAP}: exit got [{waited.stdout.strip()}] want 0 [{waited.stderr.strip()}]"


@pytest.fixture(scope="module")
def registry():
    from mlflow import MlflowClient

    uri = f"http://localhost:{_env('MLFLOW_HTTP_PORT')}"
    _wait(lambda: urllib.request.urlopen(f"{uri}/health", timeout=5).status == 200)
    client = MlflowClient(uri, uri)
    yield uri, client
    if client.search_registered_models(filter_string=f"name = '{NAME}'"):
        client.delete_registered_model(NAME)


def test_the_server_is_alive_and_ready():
    assert _call("/v2/health/live") == {}
    assert _call("/v2/health/ready") == {}


def test_a_release_is_served_a_broken_newer_release_falls_back_and_a_preview_is_served_apart(registry):
    uri, client = registry
    good = register_project(example_project("wasm/accumulate"), NAME, uri, aliases=())
    _release(client, good, "1.0.0")
    _wait(lambda: _index().get(NAME) == ("1.0.0", "READY"))
    broken = _broken_version(uri, client)
    client.set_registered_model_alias(NAME, "release", broken)
    time.sleep(8)
    assert _index().get(NAME) == ("1.0.0", "READY")
    preview = register_project(example_project("wasm/saturate"), NAME, uri, aliases=("preview",))
    assert preview not in (good, broken)
    _wait(lambda: _index().get(NAME + "_preview", ("", ""))[0].startswith("preview-"))
    assert _call(f"/v2/models/{NAME}_preview/infer", {"inputs": [{"name": "saturate_in", "shape": [1], "datatype": "FP64", "data": [-3.0]}]})["outputs"][0]["data"] == pytest.approx(
        [-3.6205930145794656]
    )
    client.delete_registered_model_alias(NAME, "preview")
    _wait(lambda: NAME + "_preview" not in _index())
    client.delete_registered_model_alias(NAME, "release")
    _wait(lambda: NAME not in _index())


def _broken_version(uri, client):
    import mlflow

    project_dir = example_project("wasm/accumulate")
    with open(join(project_dir, "model.wasm"), "ab") as model_file:
        model_file.write(b"\0")
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(NAME)
    with mlflow.start_run() as run:
        mlflow.log_artifacts(project_dir, artifact_path="project")
    tags = {"content_sha256": "0" * 64, "project_flavour": "wasm", "release_version": "2.0.0"}
    return client.create_model_version(NAME, f"{run.info.artifact_uri}/project", run_id=run.info.run_id, tags=tags).version


def _release(client, version, label):
    client.set_model_version_tag(NAME, version, "release_version", label)
    client.set_registered_model_alias(NAME, "release", version)


def _index():
    return {entry["name"]: (entry["version"], entry["state"]) for entry in _call("/v2/repository/index", {})}


def _wait(condition):
    deadline = time.monotonic() + TIMEOUT_POLL
    while time.monotonic() < deadline:
        try:
            if condition():
                return
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(1)
    raise AssertionError("condition not met in time")


def _env(name):
    with open(join(DIR_ROOT, ".env")) as env_file:
        value = ""
        for line in env_file:
            if line.startswith(f"{name}="):
                value = line.split("=", 1)[1].strip()
    assert value, f"no [{name}] in the generated .env"
    return value


def _call(path, body=None):
    url = f"http://localhost:{_env('MLSERVER_HTTP_PORT')}{path}"
    request = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        text = response.read().decode()
    return json.loads(text) if text else {}


if __name__ == "__main__":
    sys.exit(pytest.main(["-s", "-v", "--durations=50", "-o", f"cache_dir={join(DIR_ROOT, 'target/.pytest_cache')}", __file__]))
