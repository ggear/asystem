import filecmp
import json
import keyword
import os
import re
import shutil
import subprocess
import sys
import tomllib
from os.path import abspath, basename, dirname, isdir, isfile, join, relpath

from mlmodels import _constants as constants
from mlmodels._constants import CONSUMER_MODEL_PATH, PROJECT_MANIFEST, PROJECT_SIGNATURE
from mlmodels._errors import GateError
from mlmodels._metadata import PROJECT_DIR, TARGET_MATRIX, content_sha256
from mlmodels._release import consumers, released_metadata, slots, stale_slots, workspaces
from mlmodels._release import slot_name as _slot_name
from mlmodels._signature import banner, render_go, render_python, render_rust

LOADER_PACKAGES = {"mlserver": "serving"}

VOCABULARY_SERVICES = ("mlserver",)

RUSTFMT = ["rustfmt", "--edition", "2021"]

PYFMT = [join(dirname(sys.executable), "ruff"), "format", "-"]

REGISTRY_VOCABULARY = (
    "PROJECT_ALIAS_PREVIEW",
    "PROJECT_ALIAS_RELEASE",
    "PROJECT_PREVIEW_SUFFIX",
    "PROJECT_TAG_CONTENT_SHA256",
    "PROJECT_TAG_FLAVOUR",
    "PROJECT_TAG_RELEASE_VERSION",
    "PROJECT_TAG_RELEASED_AT",
    "PROJECT_RELEASE",
    "PROJECT_SCHEMA",
    "PROJECT_LABEL_PREVIEW",
    "PROJECT_LABEL_RELEASE",
)

RESERVED_NAMES = ("loader", "model", "mod", "__init__")

RUST_REFERENCE = abspath(join(dirname(__file__), "../../rust/mlmodels"))

RUST_CRATES = ("serde", "serde_json", "sha2", "wasmi", "ort")

GO_KEYWORDS = frozenset(
    [
        "break",
        "default",
        "func",
        "interface",
        "select",
        "case",
        "defer",
        "go",
        "map",
        "struct",
        "chan",
        "else",
        "goto",
        "package",
        "switch",
        "const",
        "fallthrough",
        "if",
        "range",
        "type",
        "continue",
        "for",
        "import",
        "return",
        "var",
    ]
)

RUST_KEYWORDS = frozenset(
    [
        "as",
        "break",
        "const",
        "continue",
        "crate",
        "else",
        "enum",
        "extern",
        "false",
        "fn",
        "for",
        "if",
        "impl",
        "in",
        "let",
        "loop",
        "match",
        "mod",
        "move",
        "mut",
        "pub",
        "ref",
        "return",
        "self",
        "Self",
        "static",
        "struct",
        "super",
        "trait",
        "true",
        "type",
        "unsafe",
        "use",
        "where",
        "while",
        "async",
        "await",
        "dyn",
        "abstract",
        "become",
        "box",
        "do",
        "final",
        "macro",
        "override",
        "priv",
        "typeof",
        "unsized",
        "virtual",
        "yield",
        "try",
        "gen",
    ]
)


def embed_consumer(consumer_dir, source_dir, name):
    metadata = released_metadata(source_dir, name)
    if metadata is None:
        return "none"
    directory = workspaces(source_dir)[name]
    notebook = basename(directory)
    language = metadata["target"].get("language")
    if _reserved(notebook, language):
        raise GateError("Embed", "name", f"notebook [{notebook}] is reserved or a keyword, rename it")
    if language is not None and language not in TARGET_MATRIX:
        raise GateError("Embed", "language", f"no embedding for language [{language}]")
    released = join(directory, PROJECT_DIR)
    slot = join(consumer_dir, CONSUMER_MODEL_PATH, notebook)
    if isfile(join(slot, PROJECT_MANIFEST)) and _slot_name(slot) != name:
        raise GateError("Embed", "clash", f"slot [{notebook}] holds project [{_slot_name(slot)}] and not [{name}], rename one notebook")
    changed = not _same_tree(slot, released)
    if changed:
        shutil.rmtree(slot, ignore_errors=True)
        shutil.copytree(released, slot)
    if language is not None:
        if language != "python":
            crate = join(consumer_dir, "src/main", language, basename(abspath(consumer_dir)))
            findings = rust_loader_findings(crate) if language == "rust" else go_loader_findings(crate)
            if findings:
                raise GateError("Embed", "requirements", "; ".join(findings))
        changed = bool(_replace(*_owned(consumer_dir, language))) or changed
    return "embedded" if changed else "unchanged"


def embed_loader(consumer_dir, language):
    return _replace(*_owned(consumer_dir, language))


def stale_consumers(source_dir):
    stale = {consumer for consumer in consumers(source_dir) if stale_slots(consumer, source_dir)}
    for name, directory in workspaces(source_dir).items():
        metadata = released_metadata(source_dir, name)
        if metadata is None or name.startswith("example_"):
            continue
        target = metadata["target"]
        service = "mlserver" if target["kind"] == "served" else name.split("_")[0] if target["kind"] == "embedded" else None
        found = [join(source_dir, host, service) for host in sorted(os.listdir(source_dir)) if service is not None and isdir(join(source_dir, host, service))]
        if not found:
            continue
        consumer = found[0]
        if target["kind"] == "served":
            if _owned_findings(consumer, "python"):
                stale.add(consumer)
        elif (
            not _same_tree(join(consumer, CONSUMER_MODEL_PATH, basename(directory)), join(directory, PROJECT_DIR))
            or target.get("language") in TARGET_MATRIX
            and _owned_findings(consumer, target["language"])
        ):
            stale.add(consumer)
    return sorted(stale)


def rust_loader_findings(crate_dir):
    with open(join(RUST_REFERENCE, "Cargo.toml"), "rb") as reference_file:
        reference = tomllib.load(reference_file)
    cargo = join(crate_dir, "Cargo.toml")
    if not isfile(cargo):
        return [f"manifest absent [{cargo}]"]
    with open(cargo, "rb") as consumer_file:
        consumer = tomllib.load(consumer_file)
    findings = []
    for crate in RUST_CRATES:
        wanted = _dependency(reference["dependencies"][crate])
        found = _dependency(consumer["dependencies"][crate]) if crate in consumer.get("dependencies", {}) else None
        if found is None:
            findings.append(f"dependency [{crate}] is absent and the loader needs [{wanted}]")
        elif found["version"] != wanted["version"] or found["optional"] != wanted["optional"] or found["default-features"] != wanted["default-features"] or not wanted["features"] <= found["features"]:
            findings.append(f"dependency [{crate}] is [{found}] and the loader needs [{wanted}]")
    findings.extend(
        f"feature [{feature}] is [{consumer.get('features', {}).get(feature)}] and the loader needs [{members}]"
        for feature, members in reference["features"].items()
        if feature != "default" and consumer.get("features", {}).get(feature) != members
    )
    return findings


def loader_findings(consumer_dir, source_dir):
    findings = []
    language = None
    for slot in slots(consumer_dir):
        name = _slot_name(slot)
        notebook = basename(slot)
        metadata = released_metadata(source_dir, name)
        if metadata is None:
            findings.append(("CP006", f"the embedded model has no released workspace [{name}]"))
            continue
        language = metadata["target"].get("language") or language
        if _reserved(notebook, language):
            findings.append(("CP006", f"the model file name is reserved or a keyword [{notebook}]"))
        if content_sha256(slot) != metadata["content_sha256"] and language is not None:
            findings.append(("CP005", f"the model file is not the released project [{notebook}]"))
    if language is not None:
        findings.extend(_owned_findings(consumer_dir, language))
    return findings


def go_loader_findings(crate_dir):
    reference = _go_requirements(join(RUST_REFERENCE, "../../go/mlmodels/go.mod"))
    mod = join(crate_dir, "go.mod")
    if not isfile(mod):
        return [f"manifest absent [{mod}]"]
    consumer = _go_requirements(mod)
    return [f"module [{module}] is [{consumer.get(module)}] and the loader needs [{version}]" for module, version in reference.items() if consumer.get(module) != version]


def _reserved(notebook, language):
    return notebook in RESERVED_NAMES or keyword.iskeyword(notebook) or (language == "rust" and notebook in RUST_KEYWORDS) or (language == "go" and notebook in GO_KEYWORDS)


def _go_requirements(path):
    with open(path) as mod_file:
        return dict(re.findall(r"^\s*(?:require\s+)?(\S+/\S+)\s+(v\S+)", mod_file.read(), re.MULTILINE))


def _owned(consumer_dir, language):
    service = basename(abspath(consumer_dir))
    header = "\n".join(banner("#" if language == "python" else "//"))
    models = []
    for slot in slots(consumer_dir):
        with open(join(slot, PROJECT_SIGNATURE)) as signature_file:
            models.append((basename(slot), _slot_name(slot), content_sha256(slot), json.load(signature_file)))
    if language == "python":
        source = join(consumer_dir, "src/main/python")
        package = join(source, (LOADER_PACKAGES.get(service) or service), "model")
        with open(join(dirname(__file__), "runtime", "loader.py")) as loader_file:
            files: dict = {
                join(package, "loader.py"): (header + "\n" + loader_file.read(), None),
                join(package, "__init__.py"): (header + "".join(f"from . import {notebook} as {notebook}\n" for notebook, *_ in sorted(models)), None),
            }
        if service in VOCABULARY_SERVICES:
            files[join(package, "vocabulary.py")] = (header + "\n" + "".join(f"{name} = {json.dumps(getattr(constants, name))}\n" for name in REGISTRY_VOCABULARY), None)
        files.update({join(package, f"{notebook}.py"): (render_python(signature, (name, sha)), PYFMT) for notebook, name, sha, signature in models})
        return package, consumer_dir, files
    crate = join(consumer_dir, "src/main", language, service)
    if language == "rust":
        package = join(crate, "src", "model")
        with open(join(RUST_REFERENCE, "src/runtime/loader.rs")) as loader_file:
            files = {join(package, "loader.rs"): (header + "\n" + loader_file.read(), None)}
        files[join(package, "mod.rs")] = (header + "\n" + "".join(f"pub mod {module};\n" for module in sorted(["loader", *(model[0] for model in models)])), RUSTFMT)
        files.update({join(package, f"{notebook}.rs"): (render_rust(signature, (name, sha)), RUSTFMT) for notebook, name, sha, signature in models})
        return package, crate, files
    if language == "go":
        package = join(crate, "model")
        with open(join(RUST_REFERENCE, "../../go/mlmodels/runtime/loader.go")) as loader_file:
            files = {join(package, "loader.go"): (header + "\n" + loader_file.read().replace("package runtime", "package model", 1), None)}
        with open(join(crate, "go.mod")) as mod_file:
            module = re.search(r"^module (\S+)$", mod_file.read(), re.MULTILINE)
        if module is None:
            raise GateError("Embed", "requirements", "go.mod names no module")
        files.update({join(package, notebook, f"{notebook}.go"): (render_go(signature, notebook, (name, sha, f"{module.group(1)}/model")), ["gofmt"]) for notebook, name, sha, signature in models})
        return package, crate, files
    raise ValueError(f"no loader for language [{language}]")


def _replace(package, crate, files):
    empty = [path for path, (text, _) in files.items() if not text.strip("#/\n ")]
    if empty:
        raise GateError("Embed", "source", f"a generated source is empty, refusing to replace [{package}] [{empty}]")
    rendered = {path: _format(command, text, crate) if command else text for path, (text, command) in files.items()}
    changed = [path for path, text in rendered.items() if _write(path, text)]
    changed += _remove_unowned(package, set(rendered))
    return [basename(path) for path in changed]


def _remove_unowned(package, owned):
    removed = []
    for root, directories, names in os.walk(package):
        directories[:] = [directory for directory in directories if directory != "__pycache__"]
        for name in names:
            if join(root, name) not in owned:
                os.remove(join(root, name))
                removed.append(join(root, name))
    for root, _, _ in os.walk(package, topdown=False):
        if root != package and basename(root) != "__pycache__" and not os.listdir(root):
            os.rmdir(root)
    return removed


def _owned_findings(consumer_dir, language):
    package, _, files = _owned(consumer_dir, language)
    findings = []
    for path, (text, command) in files.items():
        actual = _read(path)
        if actual is None:
            findings.append(("CP005", f"a generated file is absent [{relpath(path, consumer_dir)}]"))
        elif command is None and actual != text:
            findings.append(("CP005", f"the file is not the current mlmodels copy [{relpath(path, consumer_dir)}]"))
        elif command is not None and (head := _header(text)) != _header(actual):
            findings.append(("CP005", f"the file is not generated from the embedded project [{relpath(path, consumer_dir)}] [{head}]"))
    for root, directories, names in os.walk(package):
        directories[:] = [directory for directory in directories if directory != "__pycache__"]
        findings.extend(("CP006", f"the generated directory holds a file embed does not own [{relpath(join(root, name), consumer_dir)}]") for name in names if join(root, name) not in files)
    return findings


def _header(text):
    match = re.search(r"^(?://|#) project (\S+) sha256 (\S+)$", text, re.MULTILINE)
    return match.groups() if match else (text.count("pub mod"),)


def _format(command, text, crate_dir):
    try:
        completed = subprocess.run(command, input=text, cwd=crate_dir, capture_output=True, text=True, check=False, timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        raise GateError("Embed", "format", f"[{command[0]}] unavailable [{error}]") from error
    if completed.returncode != 0:
        raise GateError("Embed", "format", f"[{command[0]}] failed [{completed.stderr.strip()}]")
    return completed.stdout


def _read(path):
    if not isfile(path):
        return None
    with open(path) as file:
        return file.read()


def _write(path, text):
    if _read(path) == text:
        return False
    os.makedirs(dirname(path), exist_ok=True)
    with open(path, "w") as target:
        target.write(text)
    return True


def _same_tree(slot, released):
    if not isdir(slot):
        return False
    comparison = filecmp.dircmp(slot, released)
    if comparison.left_only or comparison.right_only or comparison.funny_files or comparison.common_dirs:
        return False
    _, mismatch, errors = filecmp.cmpfiles(slot, released, comparison.common_files, shallow=False)
    return not mismatch and not errors


def _dependency(specification):
    if isinstance(specification, str):
        specification = {"version": specification}
    return {
        "version": specification.get("version"),
        "optional": specification.get("optional", False),
        "default-features": specification.get("default-features", True),
        "features": set(specification.get("features", [])),
    }
