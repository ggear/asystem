import json
import logging
import os
import shutil
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from os.path import isdir, isfile, join

from mlmodels._constants import CONSUMER_MODEL_PATH, PROJECT_ALIAS_PREVIEW, PROJECT_ALIAS_RELEASE, PROJECT_MANIFEST, PROJECT_NAME
from mlmodels._errors import GateError
from mlmodels._metadata import LOCAL_TARGET, METADATA_FILE, PROJECT_DIR, content_sha256, read_metadata, write_metadata
from mlmodels._registry import register_project, registry_client
from mlmodels._signature import registered_name

LOG = logging.getLogger(__name__)

NOTEBOOK_ROOT = "rue/mlmodels/src/main/notebook"


RELEASE_FIXTURES = "example"


SERVED_TIMEOUT_SECONDS = 90


def workspaces(source_dir):
    root = join(source_dir, NOTEBOOK_ROOT)
    found = {}
    for module in sorted(os.listdir(root)) if isdir(root) else []:
        for model in sorted(os.listdir(join(root, module))):
            for notebook in sorted(os.listdir(join(root, module, model))):
                directory = join(root, module, model, notebook)
                if isdir(directory) and all(PROJECT_NAME.match(part) for part in (module, model, notebook)):
                    found[registered_name(module, model, notebook)] = directory
    return found


def release_workspaces(source_dir, version, tracking_uri=None, mlserver_url=None, clock=None):
    now = (clock or (lambda: datetime.now(UTC)))().strftime("%Y-%m-%dT%H:%M:%SZ")
    released = []
    for name, directory in workspaces(source_dir).items():
        if name.startswith(RELEASE_FIXTURES + "_"):
            LOG.info("Release workspace [%s] skipped as [fixture]", name)
            continue
        if not isfile(join(directory, METADATA_FILE)):
            LOG.info("Release workspace [%s] skipped as [unpackaged]", name)
            continue
        metadata = read_metadata(directory)
        if metadata["target"] == LOCAL_TARGET:
            LOG.info("Release workspace [%s] skipped as [local]", name)
            continue
        _require_project(name, directory)
        outcome = "kept"
        if metadata["release"] is None:
            with open(join(directory, PROJECT_DIR, "signature.json")) as signature_file:
                metadata = {**metadata, "version": version, "release": {"timestamp": now, "signature": json.load(signature_file)}}
            write_metadata(directory, metadata)
            outcome = "released"
        with open(join(directory, PROJECT_DIR, PROJECT_MANIFEST)) as manifest_file:
            manifest = json.load(manifest_file)
        target = " ".join(str(metadata["target"][key]) for key in ("kind", "language") if key in metadata["target"])
        LOG.info("Release workspace [%s] model [%s] [%s] as [%s] at version [%s] %s", name, manifest.get("model_id"), manifest["provenance"]["notes"], target, metadata["version"], outcome)
        released.append(name)
        if tracking_uri is not None and metadata["target"]["kind"] == "served":
            publish_workspace(name, directory, tracking_uri, mlserver_url)
    return released


def publish_workspace(name, directory, tracking_uri, mlserver_url=None):
    metadata = read_metadata(directory)
    _require_project(name, directory)
    if metadata["release"] is None:
        raise GateError("Release", "publish", f"workspace [{name}] has no released version")
    register_project(join(directory, PROJECT_DIR), name, tracking_uri, aliases=())
    client = registry_client(tracking_uri)
    version = next(candidate for candidate in client.search_model_versions(f"name = '{name}'") if candidate.tags.get("content_sha256") == metadata["content_sha256"])
    tags = {
        "release_version": metadata["version"],
        "inputs_sha256": metadata["inputs_sha256"],
        "released_at": metadata["release"]["timestamp"],
        "metadata": json.dumps(metadata, sort_keys=True, separators=(",", ":")),
    }
    for key, value in tags.items():
        client.set_model_version_tag(name, version.version, key, value)
    if "snapshot_version" in version.tags:
        client.delete_model_version_tag(name, version.version, "snapshot_version")
    client.set_registered_model_alias(name, PROJECT_ALIAS_RELEASE, version.version)
    if PROJECT_ALIAS_PREVIEW in client.get_registered_model(name).aliases:
        client.delete_registered_model_alias(name, PROJECT_ALIAS_PREVIEW)
    LOG.info("Release workspace [%s] published as registry version [%s] with alias [release]", name, version.version)
    if mlserver_url is None:
        return "published"
    served = wait_served(mlserver_url, name, metadata["version"])
    LOG.info("Release workspace [%s] served by mlserver as [%s]", name, served)
    return served


def clear_preview(name, tracking_uri):
    client = registry_client(tracking_uri)
    if PROJECT_ALIAS_PREVIEW in client.get_registered_model(name).aliases:
        client.delete_registered_model_alias(name, PROJECT_ALIAS_PREVIEW)


def wait_served(mlserver_url, served_name, label, timeout=SERVED_TIMEOUT_SECONDS):
    deadline = time.monotonic() + timeout
    reached = False
    while time.monotonic() < deadline:
        index = served_index(mlserver_url)
        if index is not None:
            reached = True
            if index.get(served_name) == (label, "READY"):
                return "ready"
        time.sleep(1)
    if not reached:
        return "unreachable"
    raise GateError("mlserver", "index", f"model [{served_name}] label [{label}] not ready within [{timeout}] seconds, release mlserver first if it predates the sync loop")


def served_index(mlserver_url):
    request = urllib.request.Request(f"{mlserver_url}/v2/repository/index", data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return {entry["name"]: (entry.get("version"), entry.get("state")) for entry in json.load(response)}
    except (urllib.error.URLError, OSError, ValueError):
        return None


def consumers(source_dir):
    return [
        join(source_dir, module_dir, service)
        for module_dir in sorted(os.listdir(source_dir))
        if isdir(join(source_dir, module_dir))
        for service in sorted(os.listdir(join(source_dir, module_dir)))
        if isfile(join(source_dir, module_dir, service, CONSUMER_MODEL_PATH, PROJECT_MANIFEST))
    ]


def embed_consumer(consumer_dir, source_dir, name):
    metadata = _released(source_dir, name)
    if metadata is None:
        return "none"
    slot = join(consumer_dir, CONSUMER_MODEL_PATH)
    if isfile(join(slot, PROJECT_MANIFEST)) and content_sha256(slot) == metadata["content_sha256"]:
        return "unchanged"
    shutil.rmtree(slot, ignore_errors=True)
    shutil.copytree(join(workspaces(source_dir)[name], PROJECT_DIR), slot)
    return "embedded"


def slot_findings(slot_dir, source_dir):
    metadata = _released(source_dir, _slot_name(slot_dir))
    if metadata is not None and content_sha256(slot_dir) != metadata["content_sha256"]:
        return [("CP004", f"the slot is not the released project [{content_sha256(slot_dir)}] and the released one is [{metadata['content_sha256']}]")]
    return []


def stale_consumers(source_dir):
    return [consumer for consumer in consumers(source_dir) if _stale(consumer, source_dir)]


def status_lines(source_dir, tracking_uri=None, mlserver_url=None):
    lines = []
    index = served_index(mlserver_url) if mlserver_url else None
    registry = _registry_state(tracking_uri) if tracking_uri else None
    for name, directory in workspaces(source_dir).items():
        if not isfile(join(directory, METADATA_FILE)):
            continue
        metadata = read_metadata(directory)
        if metadata["release"] is None:
            continue
        label = metadata["version"]
        if metadata["target"]["kind"] == "served":
            if index is not None and index.get(name) != (label, "READY"):
                lines.append(("WARN", f"served label differs from the released one model [{name}] served [{index.get(name)}] released [{label}]"))
            if registry is not None and registry.get(name, {}).get(PROJECT_ALIAS_RELEASE) != metadata["content_sha256"]:
                lines.append(("WARN", f"registry release differs from metadata model [{name}]"))
            if registry is not None and PROJECT_ALIAS_PREVIEW in registry.get(name, {}):
                lines.append(("WARN", f"a preview alias remains model [{name}]"))
    lines.extend(("WARN", f"consumer embeds an older release module [{os.path.relpath(consumer, source_dir)}]") for consumer in stale_consumers(source_dir))
    return lines


def _stale(consumer_dir, source_dir):
    slot = join(consumer_dir, CONSUMER_MODEL_PATH)
    metadata = _released(source_dir, _slot_name(slot))
    return metadata is not None and content_sha256(slot) != metadata["content_sha256"]


def _slot_name(slot_dir):
    with open(join(slot_dir, PROJECT_MANIFEST)) as manifest_file:
        return json.load(manifest_file)["name"]


def _released(source_dir, name):
    directory = workspaces(source_dir).get(name)
    if directory is None or not isfile(join(directory, METADATA_FILE)):
        return None
    metadata = read_metadata(directory)
    return None if metadata["release"] is None else metadata


def _registry_state(tracking_uri):
    client = registry_client(tracking_uri)
    state = {}
    for model in client.search_registered_models():
        state[model.name] = {alias: client.get_model_version(model.name, version).tags.get("content_sha256") for alias, version in model.aliases.items()}
    return state


def _require_project(name, directory):
    if not isfile(join(directory, PROJECT_DIR, "project.json")):
        raise GateError("Release", "project", f"workspace [{name}] has no project beside its metadata, run fab unittest first")
