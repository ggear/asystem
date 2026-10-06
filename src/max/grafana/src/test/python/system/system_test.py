import glob
import importlib.util
import subprocess
import sys
from os.path import abspath, basename, dirname, join, realpath

import pytest
import requests

TIMEOUT = 30
TIMEOUT_WARMUP = 300
CONTAINER = "grafana"
BOOTSTRAP = "grafana_bootstrap"

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))
DIR_DASHBOARDS = join(DIR_ROOT, "src/main/resources/data/dashboards")
GENERATE = join(DIR_ROOT, "src/build/python/grafana/generate.py")

sys.path.insert(0, abspath(join(DIR_ROOT, "../../all/_/src/build/python")))
sys.argv = [GENERATE]
specification = importlib.util.spec_from_file_location("generate", GENERATE)
generate = importlib.util.module_from_spec(specification)
specification.loader.exec_module(generate)


def _env(name):
    with open(join(DIR_ROOT, ".env")) as env_file:
        value = ""
        for line in env_file:
            if line.startswith("{}=".format(name)):
                value = line.split("=", 1)[1].strip()
    assert value, "no [{}] in the generated .env".format(name)
    return value


SERVER = "http://localhost:{}".format(_env("GRAFANA_HTTP_PORT"))
CREDENTIALS = (_env("GRAFANA_USER"), _env("GRAFANA_TOKEN"))


def test_only_the_default_org_exists():
    assert [org["id"] for org in _get("/api/orgs")] == [1]


def test_every_declared_dashboard_is_served_and_nothing_else():
    assert _served() == _declared()


def test_every_folder_is_served():
    declared = {basename(path)[:-5] for path in glob.glob(join(DIR_DASHBOARDS, "folders", "*.yaml"))}
    assert declared and {folder["uid"] for folder in _get("/api/folders")} == declared


def test_the_org_home_is_the_home_dashboard():
    assert _get("/api/org/preferences")["homeDashboardUID"] == generate.HOME


def test_both_datasources_are_provisioned():
    assert {datasource["uid"] for datasource in _get("/api/datasources")} == {generate.INFLUXDB3, generate.POSTGRES}


def test_dashboards_stay_editable_in_the_ui():
    for uid in _declared():
        dashboard = _get("/apis/dashboard.grafana.app/v2/namespaces/default/dashboards/{}".format(uid))
        assert dashboard["spec"]["editable"], "{}: editable got false want true".format(uid)
        assert "grafana.app/managedBy" not in dashboard["metadata"].get("annotations", {}), \
            "{}: managedBy annotation got present want absent".format(uid)


def test_a_second_push_converges_to_the_same_state():
    before = _served()
    pushed = subprocess.run(["docker", "exec", CONTAINER, "/asystem/etc/push.sh"],
                            capture_output=True, text=True, timeout=300, check=False)
    assert pushed.returncode == 0, "push.sh: got {} want 0 [{}]".format(pushed.returncode, pushed.stderr)
    assert _served() == before


def _get(path):
    response = requests.get(SERVER + path, auth=CREDENTIALS, timeout=TIMEOUT)
    assert response.status_code == 200, "{}: got {} want 200".format(path, response.status_code)
    return response.json()


def _declared():
    return {basename(path)[:-5] for directory in ("generated", "custom")
            for path in glob.glob(join(DIR_DASHBOARDS, directory, "*.yaml"))}


def _served():
    return {dashboard["uid"] for dashboard in _get("/api/search?type=dash-db&limit=5000")}


@pytest.fixture(scope="module", autouse=True)
def bootstrapped():
    waited = subprocess.run(["docker", "wait", BOOTSTRAP], capture_output=True, text=True, timeout=TIMEOUT_WARMUP,
                            check=False)
    assert waited.stdout.strip() == "0", "{}: exit got [{}] want 0 [{}]".format(
        BOOTSTRAP, waited.stdout.strip(), waited.stderr.strip())


if __name__ == '__main__':
    sys.exit(pytest.main(["-s", "-v", "--durations=50", "-o", "cache_dir=../../../../target/.pytest_cache", __file__, ]))
