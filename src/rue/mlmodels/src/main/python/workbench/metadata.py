import hashlib
import json
import os
import re
import shutil
from glob import glob
from os.path import dirname, isfile, join, normpath, relpath

from workbench.errors import GateError

METADATA_FILE = "metadata.json"
SIGNATURE_FILE = "signature.json"
PROJECT_DIR = "project"
METADATA_SCHEMA = 1
RUNTIME_PINS = ("numpy", "scipy", "pandas", "polars", "onnx", "onnxruntime", "wasmtime", "scikit-learn", "mlflow")
CONSUMER_PINS = ("numpy", "pandas", "onnxruntime", "wasmtime", "mlflow")
TARGET_KINDS = ("served", "embedded", "local")
LOCAL_TARGET = {"kind": "local"}
REQUIREMENT_FILES = {"python": "py_deps.txt", "rust": "cargo_deps.txt", "go": "go_deps.txt"}
TARGET_LANGUAGES = ("python", "go", "rust")
HOST_LIBRARIES = {("python", "wasm"): "wasmtime", ("python", "onnx"): "onnxruntime", ("rust", "wasm"): "wasmi", ("rust", "onnx"): "ort", ("go", "wasm"): "wazero"}
HOST_FILES = {"python": "src/main/python/py_deps.txt", "rust": "src/main/rust/{host}/Cargo.toml", "go": "src/main/go/{host}/go.mod"}
TARGET_MATRIX = {"python": ("static", "wasm", "onnx", "pyfunc"), "go": ("static", "wasm", "onnx"), "rust": ("static", "wasm", "onnx")}
METADATA_ORDER = ("schema", "targets", "passed", "runtime", "snapshot_version", "released_version", "released_by", "released_at", "released_signature", "content_sha256", "inputs_sha256")
METADATA_FIELDS = {
    "schema": int,
    "inputs_sha256": str,
    "content_sha256": str,
    "released_version": (str, type(None)),
    "snapshot_version": (str, type(None)),
    "released_by": (str, type(None)),
    "released_at": (str, type(None)),
    "runtime": dict,
    "targets": list,
    "passed": list,
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
    for root, _, files in sorted(os.walk(data_dir)):
        for file_name in sorted(files):
            path = join(root, file_name)
            digest.update(relpath(path, data_dir).encode())
            with open(path, "rb") as data_file:
                digest.update(hashlib.sha256(data_file.read()).digest())
    if isfile(join(workspace_dir, SIGNATURE_FILE)):
        with open(join(workspace_dir, SIGNATURE_FILE), "rb") as signature_file:
            digest.update(hashlib.sha256(signature_file.read()).digest())
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
    with open(join(workspace_dir, METADATA_FILE), "w") as metadata_file:
        json.dump(ordered, metadata_file, indent=2)
        metadata_file.write("\n")


def record_project(workspace_dir, project_dir, targets, pins_path, version_path=None):
    if not targets:
        return None
    previous = read_metadata(workspace_dir) if isfile(join(workspace_dir, METADATA_FILE)) else {}
    with open(join(project_dir, "signature.json")) as signature_file:
        findings = signature_findings(previous.get("released_signature"), json.load(signature_file))
    if findings:
        raise GateError("Package", "signature", "; ".join(findings))
    with open(join(project_dir, "project.json")) as manifest_file:
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
    released = previous.get("released_version") if same else None
    current = None
    if version_path is not None and isfile(version_path):
        with open(version_path) as version_file:
            current = version_file.read().strip()
    snapshot = None if released else ((previous.get("snapshot_version") if same else None) or (current if current and SNAPSHOT_VERSION.match(current) else None))
    metadata = {
        "schema": METADATA_SCHEMA,
        "inputs_sha256": inputs_sha256(workspace_dir, read_pins(pins_path)),
        "content_sha256": content,
        "runtime": runtime,
        "released_version": released,
        "snapshot_version": snapshot,
        "released_by": previous.get("released_by") if same else None,
        "released_at": previous.get("released_at") if same else None,
        "released_signature": previous.get("released_signature") if same else None,
        "targets": list(targets),
        "passed": list(targets) if list(targets) == [LOCAL_TARGET] else ([target for target in previous.get("passed", []) if target in targets] if same else []),
    }
    write_metadata(workspace_dir, metadata)
    derived = derived_requirements(runtime, manifest["flavour"], metadata["targets"])
    for language, file_name in REQUIREMENT_FILES.items():
        path = join(workspace_dir, file_name)
        if language in derived:
            with open(path, "w") as requirements_file:
                requirements_file.write("".join(f"{name}\n" for name in derived[language]))
        elif isfile(path):
            os.remove(path)
    return metadata


def record_passed(workspace_dir, target):
    metadata = read_metadata(workspace_dir)
    if target in metadata["targets"] and target not in metadata["passed"]:
        write_metadata(workspace_dir, {**metadata, "passed": [*metadata["passed"], target]})


def signature_findings(released, new):
    if released is None:
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
    return findings


def inputs_changed(workspace_dir, pins_path):
    if not isfile(join(workspace_dir, METADATA_FILE)) or not isfile(join(workspace_dir, PROJECT_DIR, "project.json")):
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
    findings.extend(("MD004", message) for message in _target_findings(flavour, metadata["targets"]))
    findings.extend(("MD004", f"passed target is not a declared target [{target}]") for target in metadata["passed"] if target not in metadata["targets"])
    if metadata["released_version"] is not None and not RELEASE_VERSION.match(metadata["released_version"]):
        findings.append(("MD002", f"released version is not a release version [{metadata['released_version']}]"))
    if metadata["snapshot_version"] is not None and not SNAPSHOT_VERSION.match(metadata["snapshot_version"]):
        findings.append(("MD002", f"snapshot version is not a snapshot version [{metadata['snapshot_version']}]"))
    if metadata["snapshot_version"] is not None and metadata["released_version"] is not None:
        findings.append(("MD002", f"a released project carries a snapshot version [{metadata['snapshot_version']}]"))
    manifest_path = join(workspace_dir, PROJECT_DIR, "project.json")
    if not isfile(manifest_path):
        findings.append(("MD003", f"project missing beside the metadata [{workspace_dir}]"))
    else:
        if content_sha256(join(workspace_dir, PROJECT_DIR)) != metadata["content_sha256"]:
            findings.append(("MD003", f"project differs from the metadata content hash [{metadata['content_sha256']}]"))
        with open(manifest_path) as manifest_file:
            manifest_runtime = json.load(manifest_file).get("runtime", {})
        signature_path = join(workspace_dir, SIGNATURE_FILE)
        if isfile(signature_path):
            with open(signature_path) as workspace_file, open(join(workspace_dir, PROJECT_DIR, SIGNATURE_FILE)) as project_file:
                if json.load(workspace_file) != json.load(project_file):
                    findings.append(("MD003", f"the signature of the workspace differs from the signature of the project [{SIGNATURE_FILE}]"))
        if metadata["runtime"] != manifest_runtime:
            findings.append(("MD005", f"metadata runtime differs from the project runtime metadata {metadata['runtime']} project {manifest_runtime}"))
    if pins_path is not None:
        pinned = {package_key(name) for name in read_pins(pins_path, None)}
        findings.extend(("MD005", f"python dependency has no project wide pin [{name}]") for name in metadata["runtime"].get("python", ()) if package_key(name) not in pinned)
    derived = derived_requirements(metadata["runtime"], flavour, metadata["targets"])
    for language, file_name in REQUIREMENT_FILES.items():
        path = join(workspace_dir, file_name)
        found = None
        if isfile(path):
            with open(path) as requirements_file:
                found = [line for line in requirements_file.read().splitlines() if line]
        if found != derived.get(language):
            findings.append(("MD005", f"requirements file [{file_name}] differs from the names derived from the metadata, expected {derived.get(language)} found {found}"))
    return findings


def derived_requirements(runtime, flavour, targets):
    derived = {}
    for target in targets:
        if target["kind"] == "local":
            continue
        language = "python" if target["kind"] == "served" else target["language"]
        names = {*(runtime.get("python", ()) if language == "python" else ()), *HOST_LIBRARIES.get((language, flavour), "").split()}
        if names:
            derived[language] = sorted(names | set(derived.get(language, ())))
    return derived


def requirements(workspace_dir, flavour, pins_path, source_dir):
    metadata = read_metadata(workspace_dir)
    pinned = {package_key(name) for name in read_pins(pins_path, None)}
    source_dir = normpath(source_dir)
    module = workspace_dir.rstrip("/").split("/")[-3]
    host = "mlmodels" if module == "example" else module
    summary = []
    lines = [
        f"! {name} has no project wide pin, add {name}==<version> to [{pins_path}]"
        for name in derived_requirements(metadata["runtime"], flavour, metadata["targets"]).get("python", ())
        if package_key(name) not in pinned
    ]
    if lines:
        summary.append("python " + " ".join(line.split()[1] for line in lines))
    for target in metadata["targets"]:
        if target["kind"] != "embedded" or target["language"] == "python":
            continue
        needed = derived_requirements(metadata["runtime"], flavour, [target]).get(target["language"], [])
        paths = glob(join(source_dir, "*", host, HOST_FILES[target["language"]].format(host="consumer" if host == "mlmodels" else host)))
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
    with open(join(project_dir, "project.json"), "rb") as manifest_file:
        return hashlib.sha256(manifest_file.read()).hexdigest()


def _target_findings(flavour, targets):
    findings = []
    if LOCAL_TARGET in targets and len(targets) != 1:
        findings.append(f"local must be the only target {targets}")
    for target in targets:
        if not isinstance(target, dict) or target.get("kind") not in TARGET_KINDS:
            findings.append(f"target kind unknown [{target}]")
        elif target["kind"] == "embedded" and flavour not in TARGET_MATRIX.get(str(target.get("language")), ()):
            findings.append(f"no wrapper for flavour [{flavour}] language [{target.get('language')}]")
    return findings
