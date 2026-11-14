import hashlib
import json
import os
import re
import shutil
from glob import glob
from os.path import dirname, isfile, join, normpath, relpath

from mlmodels._constants import PROJECT_MANIFEST, PROJECT_RELEASE, PROJECT_SCHEMA, PROJECT_SIGNATURE, SIGNATURE_VERSION_FIRST, SIGNATURE_VERSION_KEY
from mlmodels._document import write_json
from mlmodels._errors import GateError
from mlmodels._lint_project import file_sha256

METADATA_FILE = "metadata.json"


PROJECT_DIR = "project"


METADATA_SCHEMA = 2


RUNTIME_PINS = ("numpy", "scipy", "pandas", "polars", "onnx", "onnxruntime", "wasmtime", "scikit-learn", "mlflow")


CONSUMER_PINS = ("numpy", "pandas", "onnxruntime", "wasmtime", "mlflow")


TARGET_KINDS = ("served", "embedded", "local")


LOCAL_TARGET = {"kind": "local"}


REQUIREMENT_FILES = {"python": "py_deps.txt"}


HOST_LIBRARIES = {("python", "wasm"): "wasmtime", ("python", "onnx"): "onnxruntime", ("rust", "wasm"): "wasmi", ("rust", "onnx"): "ort", ("go", "wasm"): "wazero"}


HOST_FILES = {"python": "src/main/python/py_deps.txt", "rust": "src/main/rust/{host}/Cargo.toml", "go": "src/main/go/{host}/go.mod"}


TARGET_MATRIX = {"python": ("static", "wasm", "onnx", "pyfunc"), "go": ("static", "wasm", "onnx"), "rust": ("static", "wasm", "onnx")}


METADATA_ORDER = ("schema", "version", "content_sha256", "inputs_sha256", "target", "release", "baseline")


METADATA_FIELDS = {
    "schema": int,
    "version": (str, type(None)),
    "content_sha256": str,
    "inputs_sha256": str,
    "target": dict,
    "release": (dict, type(None)),
}


RELEASE_VERSION = re.compile(r"^\d+\.\d+\.\d+$")


SNAPSHOT_VERSION = re.compile(r"^\d+\.\d+\.\d+-SNAPSHOT$")


def inputs_sha256(workspace_dir, pins):
    digest = hashlib.sha256()
    with open(join(workspace_dir, "notebook.ipynb")) as notebook_file:
        for cell in json.load(notebook_file)["cells"]:
            if cell["cell_type"] == "code":
                digest.update("".join(cell["source"]).encode())
                digest.update(b"\0")
    data_dir = join(workspace_dir, "data")
    live = set()
    for root, _, files in os.walk(data_dir):
        for file_name in files:
            if file_name.endswith(".json"):
                with open(join(root, file_name)) as sidecar_file:
                    if json.load(sidecar_file).get("live"):
                        live.update((join(root, file_name), join(root, file_name[: -len(".json")] + ".csv")))
    for root, _, files in sorted(os.walk(data_dir)):
        for file_name in sorted(files):
            path = join(root, file_name)
            if path in live:
                continue
            digest.update(relpath(path, data_dir).encode())
            digest.update(bytes.fromhex(file_sha256(path)))
    if isfile(join(workspace_dir, PROJECT_SIGNATURE)):
        digest.update(bytes.fromhex(file_sha256(join(workspace_dir, PROJECT_SIGNATURE))))
    digest.update(json.dumps({name: pins.get(name) for name in RUNTIME_PINS}, sort_keys=True).encode())
    return digest.hexdigest()


def read_pins(py_deps_path, names=RUNTIME_PINS):
    pins = {}
    with open(py_deps_path) as py_deps_file:
        for line in py_deps_file:
            name, separator, version = line.strip().partition("==")
            if separator and (names is None or name.lower() in names):
                pins[name.lower()] = version
    return pins


def package_key(name):
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def read_metadata(workspace_dir):
    with open(join(workspace_dir, METADATA_FILE)) as metadata_file:
        return json.load(metadata_file)


def write_metadata(workspace_dir, metadata):
    ordered = {key: metadata[key] for key in METADATA_ORDER if key in metadata}
    ordered.update({key: metadata[key] for key in sorted(metadata) if key not in ordered})
    write_json(join(workspace_dir, METADATA_FILE), ordered)


def write_release(workspace_dir, metadata):
    path = join(workspace_dir, PROJECT_DIR, PROJECT_RELEASE)
    release = metadata["release"]
    if release is None:
        if isfile(path):
            os.remove(path)
        return
    write_json(path, {"schema": PROJECT_SCHEMA, "version": metadata["version"], "released_at": release["timestamp"], "content_sha256": metadata["content_sha256"]})


def record_project(workspace_dir, project_dir, target, pins_path, version_path=None):
    if not target:
        return None
    previous = read_metadata(workspace_dir) if isfile(join(workspace_dir, METADATA_FILE)) else {}
    released_before = previous.get("release")
    baseline = previous.get("baseline") or (None if released_before is None else released_before["signature"])
    with open(join(project_dir, PROJECT_SIGNATURE)) as signature_file:
        signature = json.load(signature_file)
    findings = [] if target.get("kind") == "embedded" else signature_findings(baseline, signature)
    if findings:
        raise GateError("Package", "signature", "; ".join(findings))
    with open(join(project_dir, PROJECT_MANIFEST)) as manifest_file:
        manifest = json.load(manifest_file)
    runtime = manifest.get("runtime", {})
    pinned = {package_key(name) for name in read_pins(pins_path, None)}
    unpinned = sorted(name for name in runtime.get("python", ()) if package_key(name) not in pinned)
    if unpinned:
        raise GateError("Package", "runtime", f"python dependencies with no project wide pin {unpinned} in [{pins_path}]")
    shutil.rmtree(join(workspace_dir, PROJECT_DIR), ignore_errors=True)
    shutil.copytree(project_dir, join(workspace_dir, PROJECT_DIR))
    content = content_sha256(project_dir)
    same = previous.get("content_sha256") == content
    current = None
    if version_path is not None and isfile(version_path):
        with open(version_path) as version_file:
            current = version_file.read().strip()
    version = (previous.get("version") if same else None) or (current if current and SNAPSHOT_VERSION.match(current) else None)
    metadata = {
        "schema": METADATA_SCHEMA,
        "version": version,
        "content_sha256": content,
        "inputs_sha256": inputs_sha256(workspace_dir, read_pins(pins_path)),
        "target": target,
        "release": released_before if same else None,
    }
    if baseline is not None and target.get("kind") == "served":
        metadata["baseline"] = baseline
    write_metadata(workspace_dir, metadata)
    write_release(workspace_dir, metadata)
    derived = derived_requirements(runtime, manifest["flavour"], target)
    for language, file_name in REQUIREMENT_FILES.items():
        path = join(workspace_dir, file_name)
        if language in derived:
            with open(path, "w") as requirements_file:
                requirements_file.write("".join(f"{name}\n" for name in derived[language]))
        elif isfile(path):
            os.remove(path)
    return metadata


def read_runtime(workspace_dir):
    manifest_path = join(workspace_dir, PROJECT_DIR, PROJECT_MANIFEST)
    if not isfile(manifest_path):
        return {}
    with open(manifest_path) as manifest_file:
        return json.load(manifest_file).get("runtime", {})


def signature_findings(released, new):
    if released is None:
        return []
    missing = [label for label, signature in (("released", released), ("new", new)) if SIGNATURE_VERSION_KEY not in signature]
    if missing:
        return [f"{SIGNATURE_VERSION_KEY} is missing from the {' and '.join(missing)} signature"]
    released_version = released[SIGNATURE_VERSION_KEY]
    new_version = new[SIGNATURE_VERSION_KEY]
    if new_version < released_version:
        return [f"signature_version went down from [{released_version}] to [{new_version}]"]
    if new_version > released_version:
        return []
    findings = []
    old_entries = {entry["name"]: entry for section in ("inputs", "outputs") for entry in released[section]}
    new_inputs = {entry["name"]: entry for entry in new["inputs"]}
    new_outputs = {entry["name"]: entry for entry in new["outputs"]}
    for section, entries in (("input", new_inputs), ("output", new_outputs)):
        released_entries = {entry["name"]: entry for entry in released[section + "s"]}
        findings.extend(f"{section} [{name}] was released and is gone or changed" for name, entry in released_entries.items() if entries.get(name) != entry)
        if section == "input":
            findings.extend(f"input [{name}] is new and required" for name, entry in entries.items() if name not in old_entries and entry["parameters"]["required"])
    if released["parameters"].get("state") != new["parameters"].get("state"):
        findings.append("state slots changed")
    if findings:
        findings.append(f"raise signature_version above [{released_version}] to make a breaking change")
    return findings


def inputs_changed(workspace_dir, pins_path):
    if not isfile(join(workspace_dir, METADATA_FILE)) or not isfile(join(workspace_dir, PROJECT_DIR, PROJECT_MANIFEST)):
        return True
    return read_metadata(workspace_dir).get("inputs_sha256") != inputs_sha256(workspace_dir, read_pins(pins_path))


def lint_metadata(workspace_dir, flavour, pins_path=None):
    metadata_path = join(workspace_dir, METADATA_FILE)
    if not isfile(metadata_path):
        return [("MD001", f"metadata missing [{metadata_path}]")]
    try:
        metadata = read_metadata(workspace_dir)
    except ValueError as error:
        return [("MD001", f"metadata is not valid JSON [{error}]")]
    if metadata.get("schema") != METADATA_SCHEMA:
        return [("MD001", f"metadata schema unsupported [{metadata.get('schema')}]")]
    findings = [("MD002", f"metadata field missing or of the wrong type [{field}]") for field, kind in METADATA_FIELDS.items() if not isinstance(metadata.get(field), kind)]
    if findings:
        return findings
    target = metadata["target"]
    if target.get("kind") not in TARGET_KINDS:
        findings.append(("MD004", f"target kind unknown [{target}]"))
    elif target["kind"] == "embedded" and flavour not in TARGET_MATRIX.get(str(target.get("language")), ()):
        findings.append(("MD004", f"no wrapper for flavour [{flavour}] language [{target.get('language')}]"))
    findings.extend(("MD006", message) for message in _signature_version_findings(workspace_dir, metadata))
    release = metadata["release"]
    if release is None:
        if metadata["version"] is not None and not SNAPSHOT_VERSION.match(metadata["version"]):
            findings.append(("MD002", f"an unreleased project has a version that is not a snapshot version [{metadata['version']}]"))
    else:
        if not isinstance(release.get("timestamp"), str) or not isinstance(release.get("signature"), dict):
            findings.append(("MD002", "release field missing or of the wrong type [timestamp] [signature]"))
        if metadata["version"] is None or not RELEASE_VERSION.match(metadata["version"]):
            findings.append(("MD002", f"a released project has a version that is not a release version [{metadata['version']}]"))
    manifest_path = join(workspace_dir, PROJECT_DIR, PROJECT_MANIFEST)
    if not isfile(manifest_path):
        findings.append(("MD003", f"project missing beside the metadata [{workspace_dir}]"))
        return findings
    if content_sha256(join(workspace_dir, PROJECT_DIR)) != metadata["content_sha256"]:
        findings.append(("MD003", f"project differs from the metadata content hash [{metadata['content_sha256']}]"))
    signature_path = join(workspace_dir, PROJECT_SIGNATURE)
    if isfile(signature_path):
        with open(signature_path) as workspace_file, open(join(workspace_dir, PROJECT_DIR, PROJECT_SIGNATURE)) as project_file:
            if json.load(workspace_file) != json.load(project_file):
                findings.append(("MD003", f"the signature of the workspace differs from the signature of the project [{PROJECT_SIGNATURE}]"))
    runtime = read_runtime(workspace_dir)
    if pins_path is not None:
        pinned = {package_key(name) for name in read_pins(pins_path, None)}
        findings.extend(("MD005", f"python dependency has no project wide pin [{name}]") for name in runtime.get("python", ()) if package_key(name) not in pinned)
    derived = derived_requirements(runtime, flavour, metadata["target"])
    for language, file_name in REQUIREMENT_FILES.items():
        path = join(workspace_dir, file_name)
        found = None
        if isfile(path):
            with open(path) as requirements_file:
                found = [line for line in requirements_file.read().splitlines() if line]
        if found != derived.get(language):
            findings.append(("MD005", f"requirements file [{file_name}] differs from the names derived from the project, expected {derived.get(language)} found {found}"))
    return findings


def _signature_version_findings(workspace_dir, metadata):
    served = metadata["target"].get("kind") == "served"
    findings = []
    if "baseline" in metadata and (not isinstance(metadata["baseline"], dict) or not served):
        findings.append("baseline needs a served target and an object")
    signature_path = join(workspace_dir, PROJECT_SIGNATURE)
    if isfile(signature_path):
        with open(signature_path) as signature_file:
            version = json.load(signature_file).get(SIGNATURE_VERSION_KEY)
        valid = isinstance(version, int) and not isinstance(version, bool) and version >= SIGNATURE_VERSION_FIRST
        if not valid:
            findings.append(f"a signature_version of [{SIGNATURE_VERSION_FIRST}] or more is needed, found [{version}]")
    return findings


def derived_requirements(runtime, flavour, target):
    if target["kind"] == "local":
        return {}
    language = "python" if target["kind"] == "served" else target["language"]
    names = {*(runtime.get("python", ()) if language == "python" else ()), *HOST_LIBRARIES.get((language, flavour), "").split()}
    return {language: sorted(names)} if names else {}


def requirements(workspace_dir, flavour, pins_path, source_dir):
    metadata = read_metadata(workspace_dir)
    runtime = read_runtime(workspace_dir)
    target = metadata["target"]
    pinned = {package_key(name) for name in read_pins(pins_path, None)}
    source_dir = normpath(source_dir)
    module = workspace_dir.rstrip("/").split("/")[-3]
    host = "mlmodels" if module == "example" else module
    summary = []
    lines = [
        f"! {name} has no project wide pin, add {name}==<version> to [{pins_path}]" for name in derived_requirements(runtime, flavour, target).get("python", ()) if package_key(name) not in pinned
    ]
    if lines:
        summary.append("python " + " ".join(line.split()[1] for line in lines))
    if target["kind"] == "embedded" and target["language"] != "python":
        needed = derived_requirements(runtime, flavour, target).get(target["language"], [])
        paths = glob(join(source_dir, "*", host, HOST_FILES[target["language"]].format(host=host)))
        declared = ""
        if len(paths) == 1:
            with open(paths[0]) as host_file:
                declared = host_file.read()
        missing = [name for name in needed if not re.search(rf"\b{re.escape(name)}\b", declared)]
        if len(paths) != 1 or missing:
            summary.append(f"{target['language']} {' '.join(missing or needed)}")
            lines.append(
                f"embedded {target['language']} host [{host}] " + (f"file [{relpath(paths[0], dirname(source_dir))}]" if len(paths) == 1 else f"no unique file under [{source_dir}] found {paths}")
            )
            lines.extend(f"  + {name}" for name in missing)
    return sum(line.startswith("  +") for line in lines), ", ".join(summary), lines


def content_sha256(project_dir):
    return file_sha256(join(project_dir, PROJECT_MANIFEST))
