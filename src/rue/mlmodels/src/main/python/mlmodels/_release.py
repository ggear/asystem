import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from os.path import isdir, isfile, join

from mlmodels._constants import (
    CONSUMER_MODEL_PATH,
    PROJECT_ALIAS_PREVIEW,
    PROJECT_ALIAS_RELEASE,
    PROJECT_MANIFEST,
    PROJECT_NAME,
    PROJECT_SIGNATURE,
    PROJECT_TAG_CONTENT_SHA256,
    PROJECT_TAG_INPUTS_SHA256,
    PROJECT_TAG_METADATA,
    PROJECT_TAG_RELEASE_VERSION,
    PROJECT_TAG_RELEASED_AT,
    PROJECT_TAG_SNAPSHOT_VERSION,
)
from mlmodels._errors import GateError
from mlmodels._metadata import LOCAL_TARGET, METADATA_FILE, PROJECT_DIR, content_sha256, read_metadata, write_metadata
from mlmodels._registry import register_project, registry_client
from mlmodels._signature import registered_name, served_name

LOG = logging.getLogger(__name__)

NOTEBOOK_ROOT = "rue/mlmodels/src/main/notebook"


RELEASE_FIXTURES = "example"


PIN_SUFFIXES = (".yaml", ".yml", ".py", ".rs", ".go", ".sh", ".conf", ".j2")


PIN_EXCLUDED = ("target", ".go", ".git", ".venv", "node_modules", "notebook", "plans", "mlmodels")


PIN_PATTERN = re.compile(r"/v2/models/([a-z0-9_]+?)(?:_preview)?/")


LIVE_KEPT = 2


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
            with open(join(directory, PROJECT_DIR, PROJECT_SIGNATURE)) as signature_file:
                signature = json.load(signature_file)
            metadata = {**metadata, "version": version, "release": {"timestamp": now, "signature": signature}}
            if metadata["target"]["kind"] == "served":
                metadata["baseline"] = signature
            write_metadata(directory, metadata)
            outcome = "released"
        with open(join(directory, PROJECT_DIR, PROJECT_MANIFEST)) as manifest_file:
            manifest = json.load(manifest_file)
        target = " ".join(str(metadata["target"][key]) for key in ("kind", "language") if key in metadata["target"])
        LOG.info("Release workspace [%s] model [%s] [%s] as [%s] at version [%s] %s", name, manifest.get("model_id"), manifest["provenance"].get("notes", "none"), target, metadata["version"], outcome)
        released.append(name)
        if tracking_uri is not None and metadata["target"]["kind"] == "served":
            publish_workspace(name, directory, tracking_uri, mlserver_url, source_dir)
    return released


def publish_workspace(name, directory, tracking_uri, mlserver_url=None, source_dir=None):
    metadata = read_metadata(directory)
    _require_project(name, directory)
    if metadata["release"] is None:
        raise GateError("Release", "publish", f"workspace [{name}] has no released version")
    registered = served_name(name, metadata["release"]["signature"])
    register_project(join(directory, PROJECT_DIR), registered, tracking_uri, aliases=(), experiment=name)
    client = registry_client(tracking_uri)
    version = next(candidate for candidate in client.search_model_versions(f"name = '{registered}'") if candidate.tags.get(PROJECT_TAG_CONTENT_SHA256) == metadata["content_sha256"])
    tags = {
        PROJECT_TAG_RELEASE_VERSION: metadata["version"],
        PROJECT_TAG_INPUTS_SHA256: metadata["inputs_sha256"],
        PROJECT_TAG_RELEASED_AT: metadata["release"]["timestamp"],
        PROJECT_TAG_METADATA: json.dumps(metadata, sort_keys=True, separators=(",", ":")),
    }
    for key, value in tags.items():
        client.set_model_version_tag(registered, version.version, key, value)
    if PROJECT_TAG_SNAPSHOT_VERSION in version.tags:
        client.delete_model_version_tag(registered, version.version, PROJECT_TAG_SNAPSHOT_VERSION)
    client.set_registered_model_alias(registered, PROJECT_ALIAS_RELEASE, version.version)
    if PROJECT_ALIAS_PREVIEW in client.get_registered_model(registered).aliases:
        client.delete_registered_model_alias(registered, PROJECT_ALIAS_PREVIEW)
    LOG.info("Release workspace [%s] published as [%s] registry version [%s] with alias [release]", name, registered, version.version)
    if mlserver_url is None:
        return "published"
    served = wait_served(mlserver_url, registered, metadata["version"])
    LOG.info("Release workspace [%s] served by mlserver as [%s]", name, served)
    if served == "ready":
        _retire_signatures(client, name, registered, source_dir)
    return served


def _retire_signatures(client, name, published, source_dir):
    live = live_signatures(name, [model.name for model in client.search_registered_models(f"name LIKE '{name}%'", max_results=1000) if PROJECT_ALIAS_RELEASE in model.aliases])
    pinned = served_pins(source_dir, name) if source_dir is not None else {}
    for _, retired in live[LIVE_KEPT:]:
        if retired == published:
            continue
        if retired in pinned:
            LOG.warning("Release workspace [%s] keeps retired signature version [%s] as it is pinned in %s", name, retired, sorted(pinned[retired]))
            continue
        client.delete_registered_model_alias(retired, PROJECT_ALIAS_RELEASE)
        LOG.info("Release workspace [%s] retired signature version [%s]", name, retired)


def live_signatures(name, released_names):
    family = re.compile(rf"^{re.escape(name)}(?:_(\d+))?$")
    return sorted(((int(match.group(1) or 0), model) for model in released_names if (match := family.match(model))), reverse=True)


def served_pins(source_dir, name):
    family = re.compile(rf"^{re.escape(name)}(?:_\d+)?$")
    found = {}
    for root, directories, files in os.walk(source_dir):
        directories[:] = [entry for entry in directories if entry not in PIN_EXCLUDED]
        for file in files:
            if file.endswith(PIN_SUFFIXES):
                with open(join(root, file), errors="ignore") as source_file:
                    for match in PIN_PATTERN.finditer(source_file.read()):
                        if family.match(match.group(1)):
                            found.setdefault(match.group(1), set()).add(os.path.relpath(join(root, file), source_dir))
    return found


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
        if slots(join(source_dir, module_dir, service))
    ]


def slots(consumer_dir):
    root = join(consumer_dir, CONSUMER_MODEL_PATH)
    return [join(root, entry) for entry in sorted(os.listdir(root)) if isfile(join(root, entry, PROJECT_MANIFEST))] if isdir(root) else []


def slot_findings(slot_dir, source_dir):
    metadata = released_metadata(source_dir, slot_name(slot_dir))
    if metadata is not None and content_sha256(slot_dir) != metadata["content_sha256"]:
        return [("CP004", f"the slot is not the released project [{content_sha256(slot_dir)}] and the released one is [{metadata['content_sha256']}]")]
    return []


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
            served = served_name(name, metadata["release"]["signature"])
            if index is not None and index.get(served) != (label, "READY"):
                lines.append(("WARN", f"served label differs from the released one model [{served}] served [{index.get(served)}] released [{label}]"))
            if registry is not None and registry.get(served, {}).get(PROJECT_ALIAS_RELEASE) != metadata["content_sha256"]:
                lines.append(("WARN", f"registry release differs from metadata model [{served}]"))
            if registry is not None and PROJECT_ALIAS_PREVIEW in registry.get(served, {}):
                lines.append(("WARN", f"a preview alias remains model [{served}]"))
            if registry is not None:
                lines.extend(_signature_lines(name, served, registry, source_dir))
    from mlmodels._embed import stale_consumers

    lines.extend(("WARN", f"consumer embeds an older release module [{os.path.relpath(consumer, source_dir)}]") for consumer in stale_consumers(source_dir))
    return lines


def _signature_lines(name, served, registry, source_dir):
    live = live_signatures(name, [model for model, aliases in registry.items() if PROJECT_ALIAS_RELEASE in aliases])
    lines = []
    if len(live) > LIVE_KEPT:
        lines.append(("WARN", f"more than [{LIVE_KEPT}] signature versions are live model [{name}] live {[model for _, model in live]}"))
    if live and live[0][1] != served and live[0][0] > int(served.rsplit("_", 1)[1]):
        lines.append(("WARN", f"the registry holds a newer signature version than git model [{name}] registry [{live[0][1]}] git [{served}]"))
    for pinned, files in sorted(served_pins(source_dir, name).items()):
        if pinned not in [model for _, model in live]:
            lines.append(("WARN", f"a client pins a signature version that is not live model [{pinned}] in {sorted(files)}"))
        elif len(live) == LIVE_KEPT and pinned == live[-1][1]:
            lines.append(("WARN", f"a client pins the older live signature version, move it before the next bump model [{pinned}] in {sorted(files)}"))
    return lines


def stale_slots(consumer_dir, source_dir):
    for slot in slots(consumer_dir):
        metadata = released_metadata(source_dir, slot_name(slot))
        if metadata is not None and content_sha256(slot) != metadata["content_sha256"]:
            return True
    return False


def slot_name(slot_dir):
    with open(join(slot_dir, PROJECT_MANIFEST)) as manifest_file:
        return json.load(manifest_file)["name"]


def released_metadata(source_dir, name):
    directory = workspaces(source_dir).get(name)
    if directory is None or not isfile(join(directory, METADATA_FILE)):
        return None
    metadata = read_metadata(directory)
    return None if metadata["release"] is None else metadata


def _registry_state(tracking_uri):
    client = registry_client(tracking_uri)
    state = {}
    for model in client.search_registered_models():
        state[model.name] = {alias: client.get_model_version(model.name, version).tags.get(PROJECT_TAG_CONTENT_SHA256) for alias, version in model.aliases.items()}
    return state


def _require_project(name, directory):
    if not isfile(join(directory, PROJECT_DIR, PROJECT_MANIFEST)):
        raise GateError("Release", "project", f"workspace [{name}] has no project beside its metadata, run fab unittest first")
