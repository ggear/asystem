import argparse
import json
import os
import re
import subprocess
import sys
from fnmatch import fnmatch
from os.path import abspath, basename, dirname, isfile, join

from workbench.document import write_json
from workbench.metadata import SIGNATURE_FILE
from workbench.model import PROJECT_FLAVOURS, PROJECT_SPLITS, build_signature, check_name, registered_name, signature_input, signature_output

NOTEBOOK_FORMAT = 4
HEADER_LABELS = ("Intent", "Data", "Status", "Future")
HEADER_REQUIRED = ("Intent", "Data")
HEADER_WORDS = 25
NOTEBOOK_SECTIONS = ("Setup", "Data", "Explore", "Train", "Evaluate", "Package", "Register", "Pull")
NOTEBOOK_SPEC = "https://github.com/ggear/asystem/blob/master/src/rue/mlmodels/src/build/resources/doc/model.md"
NOTEBOOK_ABSOLUTE_PATH = re.compile(r"""["'](/Users/|/home/|/private/|[A-Za-z]:\\)""")
NOTEBOOK_SECRET = re.compile(r"""(?i)\b(token|password|passwd|secret|api_?key)\w*\s*=\s*["'][^"']+["']""")
NOTEBOOK_MAGIC = re.compile(r"^\s*[%!]")
NOTEBOOK_STAR_IMPORT = re.compile(r"^\s*from\s+workbench(\.\w+)?\s+import\s+\*", re.MULTILINE)
NOTEBOOK_SYS_PATH = re.compile(r"\bsys\.path\b")


def lint_notebook(path):
    with open(path) as notebook_file:
        notebook = json.load(notebook_file)
    cells = notebook.get("cells", [])
    notebook_dir = dirname(abspath(path))
    model = basename(dirname(notebook_dir))
    module = basename(dirname(dirname(notebook_dir)))
    name = basename(notebook_dir)
    findings = []

    def add(rule, message, cell=None):
        findings.append((rule, message, cell))

    if notebook.get("nbformat") != NOTEBOOK_FORMAT:
        add("NB001", f"notebook format must be [{NOTEBOOK_FORMAT}] found [{notebook.get('nbformat')}]")
    for index, cell in enumerate(cells):
        if cell["cell_type"] == "code" and (cell.get("outputs") or cell.get("execution_count") is not None):
            add("NB002", "outputs and execution counts must be stripped", index)
    findings.extend(_lint_structure(cells, module, model, name))
    findings.extend(_lint_intent(cells, notebook_dir, model))
    for index, cell in enumerate(cells):
        text = _source(cell)
        if cell["cell_type"] == "code":
            for line in text.split("\n"):
                if NOTEBOOK_MAGIC.match(line):
                    add("NB007", f"magic or shell line [{line.strip()}]", index)
                if NOTEBOOK_ABSOLUTE_PATH.search(line):
                    add("NB007", f"absolute path [{line.strip()}]", index)
                if NOTEBOOK_SECRET.search(line):
                    add("NB007", "possible secret in source", index)
            if NOTEBOOK_STAR_IMPORT.search(text):
                add("NB011", "import from workbench by name, never with *", index)
            if NOTEBOOK_SYS_PATH.search(text):
                add("NB012", "the kernel puts workbench on the path, a notebook must not extend sys.path", index)
        elif any(row.startswith("|") and "**" in row for row in text.split("\n")):
            add("NB009", "bold in a table cell", index)
    data = _title_blocks(_title_text(cells))[0].get("Data", [])
    ignored_data = _ignored(notebook_dir, "data", "training", "capture", "capture", "file.csv")
    ignored_project = _ignored(notebook_dir, "project", "file")
    if (ignored_data or ignored_project) and not (data and data[0].startswith("Personal data")):
        add("NB014", "the first Data point of a workspace with git-ignored data must open with [Personal data]")
    if ignored_project and not any("`project/`" in point for point in data):
        add("NB014", "the Data points of a workspace with a git-ignored project must name [`project/`]")
    return findings


def fix_notebook(path):
    with open(path) as notebook_file:
        notebook = json.load(notebook_file)
    changed = False
    for cell in notebook.get("cells", []):
        if cell["cell_type"] == "code" and (cell.get("outputs") or cell.get("execution_count") is not None):
            cell["outputs"] = []
            cell["execution_count"] = None
            changed = True
    if changed:
        with open(path, "w") as notebook_file:
            json.dump(notebook, notebook_file, indent=1, ensure_ascii=False)
            notebook_file.write("\n")
    return changed


def scaffold_notebook(root, module, model, notebook, flavour, local=False):
    for part in (module, model, notebook):
        check_name(part)
    if flavour not in PROJECT_FLAVOURS:
        raise ValueError(f"flavour unknown [{flavour}]")
    notebook_dir = join(root, module, model, notebook)
    notebook_path = join(notebook_dir, "notebook.ipynb")
    if isfile(notebook_path):
        raise ValueError(f"notebook already exists [{notebook_path}]")
    name = registered_name(module, model, notebook)
    for split in PROJECT_SPLITS:
        os.makedirs(join(notebook_dir, "data", split), exist_ok=True)
    created = [notebook_path, join(notebook_dir, SIGNATURE_FILE)]
    for split in PROJECT_SPLITS:
        keep = join(notebook_dir, "data", split, ".gitkeep")
        if not isfile(keep):
            open(keep, "w").close()
            created.append(keep)
    with open(notebook_path, "w") as notebook_file:
        json.dump(_scaffold_notebook(module, model, notebook, name, flavour, local), notebook_file, indent=1, ensure_ascii=False)
        notebook_file.write("\n")
    signature = build_signature(
        name,
        [signature_input(f"{model}_in", "none", "An input.")],
        [signature_output(f"{model}_out", "none", "An output.", datatype="FP64")],
    )
    write_json(created[1], signature)
    return created


def main(arguments=None):
    parser = argparse.ArgumentParser(prog="workbench.notebook")
    commands = parser.add_subparsers(dest="command")
    new = commands.add_parser("new")
    new.add_argument("module")
    new.add_argument("model")
    new.add_argument("notebook")
    new.add_argument("flavour")
    new.add_argument("--root", default="src/main/notebook")
    new.add_argument("--local", action="store_true")
    lint = commands.add_parser("lint")
    lint.add_argument("--fix", action="store_true")
    lint.add_argument("paths", nargs="+")
    argv = sys.argv[1:] if arguments is None else arguments
    options = parser.parse_args(argv if argv and argv[0] in ("new", "lint") else ["lint", *argv])
    if options.command == "new":
        try:
            for path in scaffold_notebook(options.root, options.module, options.model, options.notebook, options.flavour, options.local):
                print(f"created [{path}]")
        except ValueError as error:
            print(f"ERROR notebook command failed [new] [{error}]", file=sys.stderr)
            return 1
        return 0
    failed = False
    for path in options.paths:
        if options.fix and fix_notebook(path):
            print(f"stripped outputs [{path}]")
        for rule, message, cell in lint_notebook(path):
            failed = True
            print(f"{path} [{'cell ' + str(cell) if cell is not None else 'notebook'}] {rule} {message}", file=sys.stderr)
    return 1 if failed else 0


def _scaffold_notebook(module, model, notebook, name, flavour, local):
    def markdown(text):
        return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)}

    def code(text):
        return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": text.strip("\n").splitlines(keepends=True)}

    def section(title):
        return markdown(_section_heading(title))

    static = flavour == "static"
    target = '{"kind": "local"}' if local else '{"kind": "served"}'
    cells = [
        markdown(
            f"# {module} / {model} / {notebook}\n\n**Intent**\n- Takes `{model}_in`.\n- Outputs `{model}_out`.\n- State what the outputs are intended to be, with their units.\n\n"
            "**Data**\n- `golden` is the fixed samples and expected outputs.\n\n**Status**\n- Scaffolded, so the intent, the signature and the data are still to be written."
        ),
        section("Setup"),
        code(f'from workbench import setup_workspace\n\nws = setup_workspace("{module}/{model}/{notebook}", {target})\nCONSTANTS = {{ws.outputs[0]: 1}}\n'),
    ]
    if not static:
        cells += [
            section("Data"),
            section("Train"),
            section("Evaluate"),
        ]
    cells += [
        section("Package"),
        code(
            'from workbench import package_workspace\n\npackage_workspace(ws, "static", {ws.inputs[0]: [1.0, None], "expect": ["ok", "error"]}, trained_on="none", notes="scaffold", constants=CONSTANTS)\n'
            if static
            else 'print("no model is fitted yet, so nothing is packaged")\n'
        ),
        section("Register"),
        code("from workbench import register_workspace\n\nregister_workspace(ws)"),
    ]
    if local:
        cells = cells[:-2]
    return {
        "cells": cells,
        "metadata": {"kernelspec": {"name": "asystem", "language": "python", "display_name": "asystem (Python 3.12)"}, "language_info": {"name": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def _lint_intent(cells, notebook_dir, model):
    signature_path = join(notebook_dir, SIGNATURE_FILE)
    intent = " ".join(_title_blocks(_title_text(cells))[0].get("Intent", [])) or None
    if not isfile(signature_path) or intent is None:
        return []
    with open(signature_path) as signature_file:
        signature = json.load(signature_file)
    inputs = [entry["name"] for entry in signature["inputs"]]
    outputs = [entry["name"] for entry in signature["outputs"]]
    tokens = {name for raw in re.findall(r"`([^`]+)`", intent) for name in _expand_braces(raw)}
    findings = [
        ("NB013", f"the Intent does not name the output [{name}], list it or a pattern such as [{name.rsplit('_', 2)[0]}_{{a,b}}_x] or [prefix_*]", None)
        for name in outputs
        if not any(fnmatch(name, token) for token in tokens)
    ]
    findings.extend(
        ("NB013", f"the Intent names [{token}] which the signature does not have", None)
        for token in sorted(tokens)
        if token.startswith(f"{model}_") and "/" not in token and not any(fnmatch(name, token) for name in [*inputs, *outputs])
    )
    return findings


def _expand_braces(text):
    if "{" not in text or "}" not in text:
        return [text]
    before, _, rest = text.partition("{")
    body, _, after = rest.partition("}")
    return [before + option + after for option in body.split(",")]


def _lint_structure(cells, module, model, name):
    findings = []
    markdown = [(index, _source(cell)) for index, cell in enumerate(cells) if cell["cell_type"] == "markdown"]
    titles = [(index, text) for index, text in markdown if text.startswith("# ")]
    if len(titles) != 1:
        findings.append(("NB003", f"exactly one level-one title required, found [{len(titles)}]", None))
    else:
        index, text = titles[0]
        expected = f"# {module} / {model} / {name}"
        lines = text.split("\n")
        if lines[0] != expected:
            findings.append(("NB003", f"title must be [{expected}] found [{lines[0]}]", index))
        blocks, stray = _title_blocks(text)
        findings.extend(("NB004", f"the title cell holds only a bold label from {list(HEADER_LABELS)} and its dot points, found [{line[:50]}]", index) for line in stray[:3])
        findings.extend(("NB004", f"the title cell needs the label [{label}] and a dot point under it", index) for label in HEADER_REQUIRED if not blocks.get(label))
        findings.extend(
            ("NB004", f"the title cell dot point is over [{HEADER_WORDS}] words [{point[:40]}]", index) for points in blocks.values() for point in points if len(point.split()) > HEADER_WORDS
        )
        future = False
        for line in lines[1:]:
            label = re.match(r"^\*\*(\w+)\*\*$", line)
            if label is not None:
                future = label.group(1) == "Future"
            elif future and line.startswith("- ") and not re.match(r"^- (Overall|Phase \d+): ", line):
                findings.append(("NB004", f"a Future dot point must open with [Overall:] or its phase as [Phase 1:] found [{line[:50]}]", index))
    sections = []
    for index, text in markdown:
        first = text.split("\n")[0]
        if first.startswith("### "):
            findings.append(("NB005", "headings deeper than level two are not allowed", index))
        elif first.startswith("## "):
            section = first[3:].split(" (")[0].strip()
            sections.append(section)
            if section not in NOTEBOOK_SECTIONS:
                findings.append(("NB005", f"unknown section [{section}]", index))
            if section in NOTEBOOK_SECTIONS and text != _section_heading(section):
                findings.append(("NB006", f"section [{section}] must be only the heading [{_section_heading(section)}]", index))
    known = [NOTEBOOK_SECTIONS.index(section) for section in sections if section in NOTEBOOK_SECTIONS]
    if known != sorted(known):
        findings.append(("NB005", f"sections must be in the order {list(NOTEBOOK_SECTIONS)} found {sections}", None))
    if "Setup" not in sections:
        findings.append(("NB005", "section [Setup] is required", None))
    section_codes = {}
    current = None
    for index, cell in enumerate(cells):
        text = _source(cell)
        if cell["cell_type"] == "markdown" and text.startswith("## "):
            current = text[3:].split(" (")[0].strip()
            section_codes[current] = 0
        elif cell["cell_type"] == "code" and current is not None:
            section_codes[current] += 1
            if section_codes[current] == 2:
                findings.append(("NB015", f"section [{current}] must hold one code cell", index))
    setup = "\n".join(_source(cell) for cell in cells if cell["cell_type"] == "code")
    if not re.search(rf"""\bsetup_workspace\(\s*["']{re.escape(f"{module}/{model}/{name}")}["']""", setup):
        findings.append(("NB008", f"setup_workspace must be called with the workspace [{module}/{model}/{name}]", None))
    return findings


def _section_heading(section):
    number = f"6.7.{NOTEBOOK_SECTIONS.index(section) + 1}"
    return f"## {section} ([{number}]({NOTEBOOK_SPEC}#{number.replace('.', '')}-{section.lower().replace(' ', '-')}))"


def _title_text(cells):
    return next((_source(cell) for cell in cells if cell["cell_type"] == "markdown" and _source(cell).startswith("# ")), "")


def _title_blocks(text):
    blocks, stray, current = {}, [], None
    for line in text.split("\n")[1:]:
        label = re.match(r"^\*\*(\w+)\*\*$", line)
        point = re.match(r"^ {0,4}- (\S.*)$", line)
        if label is not None and label.group(1) in HEADER_LABELS:
            current = blocks.setdefault(label.group(1), [])
        elif point is not None and current is not None:
            current.append(point.group(1))
        elif line.strip():
            stray.append(line)
    return blocks, stray


def _ignored(notebook_dir, *parts):
    try:
        return subprocess.run(["git", "check-ignore", "-q", join(*parts)], cwd=notebook_dir, capture_output=True, timeout=10, check=False).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _source(cell):
    return "".join(cell["source"])


if __name__ == "__main__":
    sys.exit(main())
