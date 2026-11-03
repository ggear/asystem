import argparse
import json
import os
import re
import sys
from os.path import abspath, basename, dirname, isfile, join

from asystem.model import PROJECT_FLAVORS, PROJECT_SPLITS, PROJECT_VERSION_FILE, PROJECT_VERSION_FIRST, check_name, registered_name

NOTEBOOK_FORMAT = 4
NOTEBOOK_SECTIONS = ("Setup", "Capture Data", "Explore", "Fit", "Evaluate", "Package", "Register", "Pull")
NOTEBOOK_TITLE_ROWS = ("Intent", "Project Flavor", "Data Splits")
NOTEBOOK_TITLE_HEADER = "| Term | In This Notebook |"
NOTEBOOK_ABSOLUTE_PATH = re.compile(r"""["'](/Users/|/home/|/private/|[A-Za-z]:\\)""")
NOTEBOOK_SECRET = re.compile(r"""(?i)\b(token|password|passwd|secret|api_?key)\w*\s*=\s*["'][^"']+["']""")
NOTEBOOK_MAGIC = re.compile(r"^\s*[%!]")
NOTEBOOK_STAR_IMPORT = re.compile(r"^\s*from\s+library(\.\w+)?\s+import\s+\*", re.MULTILINE)
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
                add("NB011", "import from library by name, never with *", index)
            if NOTEBOOK_SYS_PATH.search(text):
                add("NB012", "the kernel puts library on the path, a notebook must not extend sys.path", index)
        elif index > 0 and any(row.startswith("|") and "**" in row for row in text.split("\n")):
            add("NB009", "bold in a table cell outside the title table", index)
    if not isfile(join(notebook_dir, "plan.md")):
        add("NB010", "plan [plan.md] is missing next to the notebook")
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


def scaffold_notebook(root, module, model, notebook, flavor):
    for part in (module, model, notebook):
        check_name(part)
    if flavor not in PROJECT_FLAVORS:
        raise ValueError(f"flavor unknown [{flavor}]")
    notebook_dir = join(root, module, model, notebook)
    notebook_path = join(notebook_dir, "notebook.ipynb")
    if isfile(notebook_path):
        raise ValueError(f"notebook already exists [{notebook_path}]")
    name = registered_name(module, model, notebook)
    for split in PROJECT_SPLITS:
        os.makedirs(join(notebook_dir, "data", split), exist_ok=True)
    created = [notebook_path, join(notebook_dir, "plan.md")]
    if flavor != "static":
        with open(join(notebook_dir, PROJECT_VERSION_FILE), "w") as version_file:
            version_file.write(f"{PROJECT_VERSION_FIRST}-SNAPSHOT\n")
        created.append(join(notebook_dir, PROJECT_VERSION_FILE))
    for split in PROJECT_SPLITS:
        keep = join(notebook_dir, "data", split, ".gitkeep")
        if not isfile(keep):
            open(keep, "w").close()
            created.append(keep)
    with open(notebook_path, "w") as notebook_file:
        json.dump(_scaffold_notebook(module, model, notebook, name, flavor), notebook_file, indent=1, ensure_ascii=False)
        notebook_file.write("\n")
    with open(created[1], "w") as plan_file:
        plan_file.write(_scaffold_plan(module, model, notebook, name, flavor))
    return created


def main(arguments=None):
    parser = argparse.ArgumentParser(prog="asystem.notebook")
    commands = parser.add_subparsers(dest="command")
    new = commands.add_parser("new")
    new.add_argument("module")
    new.add_argument("model")
    new.add_argument("notebook")
    new.add_argument("flavor")
    new.add_argument("--root", default="src/main/model")
    lint = commands.add_parser("lint")
    lint.add_argument("--fix", action="store_true")
    lint.add_argument("paths", nargs="+")
    argv = sys.argv[1:] if arguments is None else arguments
    options = parser.parse_args(argv if argv and argv[0] in ("new", "lint") else ["lint", *argv])
    if options.command == "new":
        try:
            for path in scaffold_notebook(options.root, options.module, options.model, options.notebook, options.flavor):
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
            print(f"{path}:{'cell ' + str(cell) if cell is not None else 'notebook'}: {rule} {message}", file=sys.stderr)
    return 1 if failed else 0


def _scaffold_notebook(module, model, notebook, name, flavor):
    def markdown(text):
        return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)}

    def code(text):
        return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": text.strip("\n").splitlines(keepends=True)}

    def section(title, stage, intent):
        return markdown(f"## {title}\n\n- **Stage:** {stage}\n- **Intent:** {intent}")

    static = flavor == "static"
    version_line = 'MODEL_VERSION = "static-1"' if static else "MODEL_VERSION = development_version(WORKSPACE)"
    project_import = "from library.project import provenance" if static else "from library.project import development_version, provenance"
    cells = [
        markdown(
            f"# {module} / {model} / {notebook}\n\nState in one line what this model does.\n\n| Term | In This Notebook |\n|---|---|\n"
            f"| **Intent** | State what the model is for |\n| **Project Flavor** | `{flavor}` (`spec.md` 3.2) |\n"
            f"| **Data Splits** | `golden` the fixed samples and expected outputs |"
        ),
        section("Setup", "none, preparation for the stages below.", "load `env` and declare the model name, version and dataset names as constants (`spec.md` 6.6)."),
        code(
            f"import json\nimport tempfile\nfrom os.path import join\n\nfrom library.data import golden_data\nfrom library.env import init_env\n{project_import}\n\nenv = init_env()\n\n"
            f'WORKSPACE = "{module}/{model}/{notebook}"\nMODEL_NAME = "{name}"\n{version_line}\nGOLDEN = "{model}_{notebook}_golden"\nCONSTANTS = {{"{module}_{model}_out": 1}}\n'
        ),
    ]
    if not static:
        cells += [
            section("Capture Data", "1, capture data (`spec.md` 7.1).", "load the `training` and `validation` data."),
            section("Fit", "3, fit.", "fit the model on `training` only (R6)."),
            section("Evaluate", "4, evaluate.", "check the fit on `validation` and `backtest` through the shipped runtime and run its acceptance check with `evaluate_acceptance` (R4, R14)."),
        ]
    cells += [
        section("Package", "5, package.", "write the golden samples, build the signature and write the project with its evaluation (R1, R3, R14)."),
        code(
            "from asystem.model import build_signature, signature_input, signature_output, package_project, register_project\n\n"
            f'golden_pl, golden_path = golden_data(WORKSPACE, GOLDEN, lambda: {{"{module}_{model}_in": [1.0, None], "expect": ["ok", "error"]}})\n\n'
            f'signature = build_signature(MODEL_NAME, [MODEL_VERSION], [signature_input("{module}_{model}_in", "none", "An input.")], [signature_output("{module}_{model}_out", "none", "An output.")])\n'
            'project_dir = join(tempfile.mkdtemp(), "project")\n'
            + (
                'manifest = package_project(project_dir, MODEL_NAME, MODEL_VERSION, "static", signature, golden_pl.iter_rows(named=True), provenance("manual", "none", [golden_path], "scaffold"), constants=CONSTANTS)\n'
                "print(json.dumps(manifest, indent=2))\n"
                if static
                else 'print("no model is fitted yet, so nothing is packaged")\n'
            )
        ),
        section("Register", "6, register.", "register the verified project with the alias `candidate`. A person sets `release` after review and the parity gate (R5)."),
        code('version = register_project(project_dir, MODEL_NAME, env["MLFLOW_TRACKING_URI"], aliases=("candidate",))\nprint("registered version", version)'),
    ]
    return {
        "cells": cells,
        "metadata": {"kernelspec": {"name": "asystem", "language": "python", "display_name": "asystem (Python 3.12)"}, "language_info": {"name": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def _scaffold_plan(module, model, notebook, name, flavor):
    return (
        f"# {notebook}\n\nThe plan for the `{name}` model. It follows `spec.md`, the specification for MLflow model projects.\n\n"
        f"| Term | In This Plan |\n|---|---|\n| **Module** | `{module}` |\n| **Model** | `{model}` |\n"
        f"| **Notebook** | `src/may/mlflow/src/main/model/{module}/{model}/{notebook}/notebook.ipynb` |\n"
        f"| **Registered Model** | `{name}` (`spec.md` 6.1) |\n| **Project Flavor** | `{flavor}` (`spec.md` 3.2) |\n\n"
        "**Status.** Scaffolded.\n\n## Intent\n\nState what the model is for.\n\n## Signature\n\nList the inputs and outputs.\n\n"
        "## Data\n\nName the datasets under each split.\n\n## To do\n\n1. Write the intent, the signature and the data.\n"
    )


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
        if NOTEBOOK_TITLE_HEADER not in lines:
            findings.append(("NB004", f"title table header [{NOTEBOOK_TITLE_HEADER}] is missing", index))
        else:
            terms = [re.sub(r"^\|\s*(?:\*\*)?([^*|]+?)(?:\*\*)?\s*\|.*$", r"\1", row) for row in lines[lines.index(NOTEBOOK_TITLE_HEADER) + 2 :] if row.startswith("|")]
            if tuple(terms) != NOTEBOOK_TITLE_ROWS:
                findings.append(("NB004", f"title table rows must be {list(NOTEBOOK_TITLE_ROWS)} found {terms}", index))
            if any(row.startswith("|") and not row.startswith("| **") for row in lines[lines.index(NOTEBOOK_TITLE_HEADER) + 2 :]):
                findings.append(("NB004", "the Term column of the title table must be bold", index))
    sections = []
    for index, text in markdown:
        first = text.split("\n")[0]
        if first.startswith("### "):
            findings.append(("NB005", "headings deeper than level two are not allowed", index))
        elif first.startswith("## "):
            section = first[3:].strip()
            sections.append(section)
            if section not in NOTEBOOK_SECTIONS:
                findings.append(("NB005", f"unknown section [{section}]", index))
            if not re.search(r"^- \*\*Stage:\*\* ", text, re.MULTILINE) or not re.search(r"^- \*\*Intent:\*\* ", text, re.MULTILINE):
                findings.append(("NB006", f"section [{section}] needs Stage and Intent dot points", index))
    known = [NOTEBOOK_SECTIONS.index(section) for section in sections if section in NOTEBOOK_SECTIONS]
    if known != sorted(known):
        findings.append(("NB005", f"sections must be in the order {list(NOTEBOOK_SECTIONS)} found {sections}", None))
    if "Setup" not in sections:
        findings.append(("NB005", "section [Setup] is required", None))
    setup = "\n".join(_source(cell) for cell in cells if cell["cell_type"] == "code")
    for constant, value in (("WORKSPACE", f"{module}/{model}/{name}"), ("MODEL_NAME", f"{module}_{model}_{name}")):
        if not re.search(rf"""^{constant}\s*=\s*["']{re.escape(value)}["']""", setup, re.MULTILINE):
            findings.append(("NB008", f"constant [{constant}] must be [{value}]", None))
    return findings


def _source(cell):
    return "".join(cell["source"])


if __name__ == "__main__":
    sys.exit(main())
