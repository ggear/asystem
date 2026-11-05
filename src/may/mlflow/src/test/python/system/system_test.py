import sys
import tempfile
import time
import urllib.error
import urllib.request
from os.path import abspath, dirname, join, realpath

import pytest

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
TIMEOUT_POLL = 90
UPLOAD_BYTES = 30 * 1024 * 1024
NAME = "mlflow_system_test"


@pytest.fixture(scope="module")
def registry():
    from mlflow import MlflowClient

    uri = f"http://localhost:{_env('MLFLOW_HTTP_PORT')}"
    _wait(lambda: urllib.request.urlopen(f"{uri}/health", timeout=5).status == 200)
    client = MlflowClient(uri, uri)
    yield uri, client
    if client.search_registered_models(filter_string=f"name = '{NAME}'"):
        client.delete_registered_model(NAME)


def test_the_server_is_healthy(registry):
    uri, _ = registry
    with urllib.request.urlopen(f"{uri}/health", timeout=30) as response:
        assert response.status == 200


def test_a_model_version_is_registered_with_an_alias_and_tags(registry):
    _, client = registry
    client.create_registered_model(NAME)
    run = client.create_run(client.create_experiment(f"{NAME}_{time.time_ns()}"))
    version = client.create_model_version(NAME, f"{run.info.artifact_uri}/model", run_id=run.info.run_id, tags={"content_sha256": "0" * 64}).version
    client.set_registered_model_alias(NAME, "preview", version)
    found = client.get_model_version_by_alias(NAME, "preview")
    assert found.version == version
    assert found.tags["content_sha256"] == "0" * 64


def test_an_artifact_larger_than_the_default_body_limit_is_uploaded(registry):
    import mlflow

    uri, client = registry
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(NAME)
    with tempfile.TemporaryDirectory() as work_dir, mlflow.start_run() as run:
        with open(join(work_dir, "large.bin"), "wb") as large_file:
            large_file.write(b"\0" * UPLOAD_BYTES)
        mlflow.log_artifact(join(work_dir, "large.bin"))
    assert client.list_artifacts(run.info.run_id)[0].file_size == UPLOAD_BYTES


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


if __name__ == "__main__":
    sys.exit(pytest.main(["-s", "-v", "--durations=50", "-o", f"cache_dir={join(DIR_ROOT, 'target/.pytest_cache')}", __file__]))
