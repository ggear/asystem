import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from os.path import abspath, dirname, join, realpath

sys.path.append("../../../main/python")

import pytest

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))


@pytest.fixture(autouse=True, scope="session")
def _server_is_up():
    deadline = time.monotonic() + 300
    while True:
        try:
            _call("/v2/health/ready")
            return
        except (OSError, urllib.error.URLError):
            if time.monotonic() > deadline:
                raise
            time.sleep(2)


def test_the_server_is_alive_and_ready():
    assert _call("/v2/health/live") == {}
    assert _call("/v2/health/ready") == {}


def test_every_listed_model_is_ready():
    index = _call("/v2/repository/index", {})
    assert all(entry["state"] == "READY" for entry in index), index


def test_every_served_model_answers_its_golden_file():
    from mlflow.artifacts import download_artifacts

    import mlflow

    mlflow.set_tracking_uri(_env("MLFLOW_TRACKING_URI"))
    mlflow.set_registry_uri(_env("MLFLOW_TRACKING_URI"))
    for entry in _call("/v2/repository/index", {}):
        staging_dir = tempfile.mkdtemp()
        download_artifacts(artifact_uri=f"models:/{entry['name']}@release", dst_path=staging_dir)
        golden_path = next(join(root, "golden.json") for root, _, files in os.walk(staging_dir) if "golden.json" in files)
        with open(golden_path) as golden_file:
            golden = json.load(golden_file)
        for sequence in golden["sequences"]:
            for step in sequence["steps"]:
                if "error" in step:
                    continue
                answer = _call(f"/v2/models/{entry['name']}/infer", step["request"])
                served = {output["name"]: output["data"] for output in answer["outputs"]}
                for output in step["response"]["outputs"]:
                    bounds = golden.get("tolerance", {}).get(output["name"], {})
                    assert all(abs(a - b) <= bounds.get("absolute", 0.0) + bounds.get("relative", 0.0) * abs(b) for a, b in zip(served[output["name"]], output["data"], strict=True))


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
    sys.exit(
        pytest.main(
            [
                "-s",
                "-v",
                "--durations=50",
                "-o",
                f"cache_dir={join(DIR_ROOT, 'target/.pytest_cache')}",
                __file__,
            ]
        )
    )
