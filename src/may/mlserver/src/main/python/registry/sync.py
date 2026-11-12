import json
import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
from os.path import isdir, join

from registry.report import stage, subject
from serving.model.loader import load
from serving.model.vocabulary import (
    PROJECT_ALIAS_PREVIEW,
    PROJECT_ALIAS_RELEASE,
    PROJECT_LABEL_PREVIEW,
    PROJECT_LABEL_RELEASE,
    PROJECT_PREVIEW_SUFFIX,
    PROJECT_RELEASE,
    PROJECT_SCHEMA,
    PROJECT_TAG_CONTENT_SHA256,
    PROJECT_TAG_FLAVOUR,
    PROJECT_TAG_RELEASE_VERSION,
    PROJECT_TAG_RELEASED_AT,
)

RUNTIME = "serving.runtime.ProjectRuntime"
SERVER_SETTINGS = {"host": "0.0.0.0", "http_port": 8080, "grpc_port": 8081, "parallel_workers": 0}
SETTINGS_FILE = "model-settings.json"
POLL_SECONDS = 30


class MlflowRegistry:
    def __init__(self, tracking_uri):
        import mlflow
        from mlflow import MlflowClient

        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_registry_uri(tracking_uri)
        self.client = MlflowClient()

    def models(self):
        versions = {}
        for version in self._pages(self.client.search_model_versions):
            versions.setdefault(version.name, {})[str(version.version)] = dict(version.tags)
        return [{"name": model.name, "aliases": dict(model.aliases), "versions": versions.get(model.name, {})} for model in self._pages(self.client.search_registered_models)]

    @staticmethod
    def _pages(search):
        token = None
        while True:
            page = search(page_token=token)
            yield from page
            token = page.token
            if not token:
                return

    def download(self, name, version, destination):
        from mlflow.artifacts import download_artifacts

        download_artifacts(artifact_uri=f"models:/{name}/{version}", dst_path=destination)


def main(arguments=None):
    arguments = sys.argv[1:] if arguments is None else arguments
    tracking_uri = os.environ["MLFLOW_TRACKING_URI"]
    models_dir = os.environ["MLFLOW_MODEL_DIR"]
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "60")
    os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "2")
    server = f"http://localhost:{SERVER_SETTINGS['http_port']}"
    interval = int(os.environ.get("MLSERVER_POLL_SECONDS", POLL_SECONDS))
    os.makedirs(models_dir, exist_ok=True)
    for entry in os.listdir(models_dir):
        if entry.startswith("."):
            shutil.rmtree(join(models_dir, entry), ignore_errors=True)
    with open(join(models_dir, "settings.json"), "w") as settings_file:
        json.dump(SERVER_SETTINGS, settings_file, indent=2, sort_keys=True)
    registry = MlflowRegistry(tracking_uri)
    failed = set()
    if "--once" in arguments:
        sync(registry, models_dir, failed)
        return 0
    _log("INFO", f"polling registry every [{interval}] seconds")
    while True:
        sync(registry, models_dir, failed, lambda action, name: _call(server, action, name))
        time.sleep(interval)


def sync(registry, models_dir, failed, call=None):
    try:
        wanted = _wanted(registry.models())
    except Exception as error:
        _log("WARN", f"registry unreachable, loaded models stay [{error}]")
        return
    held = _held(models_dir)
    for served, candidates in wanted.items():
        _serve(registry, models_dir, served, candidates, held.get(served), failed, call)
    for served in held.keys() - wanted.keys():
        try:
            with subject(f"unload {served}"):
                with stage("unload") as entry:
                    if call is not None and call("unload", served) is False:
                        raise OSError("the server refused the unload")
                    entry.detail = "server" if call is not None else "at start"
                with stage("remove") as entry:
                    shutil.rmtree(join(models_dir, served), ignore_errors=True)
                    entry.detail = "files"
        except OSError as error:
            _log("WARN", f"unload refused, files kept for the next poll model [{served}] [{error}]")


def _wanted(models):
    wanted = {}
    for model in models:
        versions, aliases = model["versions"], model["aliases"]
        released = aliases.get(PROJECT_ALIAS_RELEASE)
        if released is not None and _is_mlmodels(versions.get(str(released))):
            tags = versions[str(released)]
            older = sorted((int(version) for version, other in versions.items() if PROJECT_TAG_RELEASE_VERSION in other and int(version) < int(released)), reverse=True)
            wanted[model["name"]] = [(str(released), tags, tags.get(PROJECT_TAG_RELEASE_VERSION) or f"{PROJECT_LABEL_RELEASE}{tags[PROJECT_TAG_CONTENT_SHA256][:8]}")]
            wanted[model["name"]] += [(str(number), versions[str(number)], versions[str(number)][PROJECT_TAG_RELEASE_VERSION]) for number in older]
        previewed = aliases.get(PROJECT_ALIAS_PREVIEW)
        if previewed is not None and str(previewed) != str(released) and _is_mlmodels(versions.get(str(previewed))):
            tags = versions[str(previewed)]
            wanted[model["name"] + PROJECT_PREVIEW_SUFFIX] = [(str(previewed), tags, f"{PROJECT_LABEL_PREVIEW}{tags[PROJECT_TAG_CONTENT_SHA256][:8]}")]
    return wanted


def _is_mlmodels(tags):
    return tags is not None and PROJECT_TAG_CONTENT_SHA256 in tags and PROJECT_TAG_FLAVOUR in tags


def _held(models_dir):
    held = {}
    for entry in os.listdir(models_dir) if isdir(models_dir) else []:
        settings_path = join(models_dir, entry, SETTINGS_FILE)
        if os.path.isfile(settings_path):
            with open(settings_path) as settings_file:
                held[entry] = json.load(settings_file)["parameters"].get("extra", {})
    return held


def _serve(registry, models_dir, served, candidates, held, failed, call):
    name = served.removesuffix(PROJECT_PREVIEW_SUFFIX)
    for version, tags, label in candidates:
        if (served, version) in failed:
            continue
        if held is not None and held.get("registry_version") == version and held.get("content_sha256") == tags[PROJECT_TAG_CONTENT_SHA256]:
            return
        try:
            with subject(f"sync {served}"):
                _swap(registry, models_dir, served, name, version, tags, label, call)
        except Exception as error:
            failed.add((served, version))
            _log("WARN", f"version not usable model [{served}] version [{version}] [{error}]")
            continue
        return
    if held is None:
        _log("ERROR", f"no usable version model [{served}]")


def _swap(registry, models_dir, served, name, version, tags, label, call):
    staging_dir = tempfile.mkdtemp(prefix=f".{served}-", dir=models_dir)
    try:
        with stage("download") as entry:
            registry.download(name, version, staging_dir)
            project_dir = next((root for root, _, files in os.walk(staging_dir) if "project.json" in files), None)
            if project_dir is None:
                raise ValueError("no project in the pulled model")
            entry.detail = f"v{version}"
        with stage("verify") as entry:
            if PROJECT_TAG_RELEASE_VERSION in tags and PROJECT_TAG_RELEASED_AT in tags:
                release = {"schema": PROJECT_SCHEMA, "version": tags[PROJECT_TAG_RELEASE_VERSION], "released_at": tags[PROJECT_TAG_RELEASED_AT], "content_sha256": tags[PROJECT_TAG_CONTENT_SHA256]}
                with open(join(project_dir, PROJECT_RELEASE), "w") as release_file:
                    json.dump(release, release_file, indent=2)
            model = load(project_dir)
            entry.detail = f"content {tags[PROJECT_TAG_CONTENT_SHA256][:8]} label {label}"
        target_dir = join(models_dir, served)
        backup_dir = join(staging_dir, "previous")
        with stage("install") as entry:
            settings = {
                "name": served,
                "implementation": RUNTIME,
                "parameters": {"version": label, "extra": {"registry_version": version, "content_sha256": tags[PROJECT_TAG_CONTENT_SHA256]}},
                "inputs": [{key: entry[key] for key in ("name", "datatype", "shape")} for entry in model.signature()["inputs"]],
                "outputs": [{key: entry[key] for key in ("name", "datatype", "shape")} for entry in model.signature()["outputs"]],
            }
            with open(join(project_dir, SETTINGS_FILE), "w") as settings_file:
                json.dump(settings, settings_file, indent=2, sort_keys=True)
            if isdir(target_dir):
                os.rename(target_dir, backup_dir)
            os.rename(project_dir, target_dir)
            entry.detail = f"label {label}"
        with stage("load") as entry:
            if call is not None and call("load", served) is False:
                shutil.rmtree(target_dir, ignore_errors=True)
                if isdir(backup_dir):
                    os.rename(backup_dir, target_dir)
                raise ValueError("the server refused the load")
            entry.detail = "server" if call is not None else "at start"
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def _call(server, action, name):
    request = urllib.request.Request(f"{server}/v2/repository/models/{name}/{action}", data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=120):
            return True
    except urllib.error.HTTPError as error:
        _log("WARN", f"server refused action [{action}] model [{name}] [{error}]")
        return False
    except OSError as error:
        _log("WARN", f"server unreachable action [{action}] model [{name}], it loads from disk at start [{error}]")
        return None


def _log(level, message):
    print(f"{level} {message}", file=sys.stderr if level != "INFO" else sys.stdout, flush=True)


if __name__ == "__main__":
    sys.exit(main())
