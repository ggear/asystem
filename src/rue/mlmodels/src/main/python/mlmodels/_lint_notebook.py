import ast
import builtins
import json
import re
import subprocess
from fnmatch import fnmatch
from os.path import abspath, basename, dirname, isfile, join

from mlmodels._constants import (
    HEADER_LABELS,
    HEADER_REQUIRED,
    HEADER_WORDS,
    NOTEBOOK_ABSOLUTE_PATH,
    NOTEBOOK_FORMAT,
    NOTEBOOK_MAGIC,
    NOTEBOOK_PLOT,
    NOTEBOOK_RENAME,
    NOTEBOOK_SECRET,
    NOTEBOOK_SPEC,
    NOTEBOOK_STAGES,
    NOTEBOOK_STAR_IMPORT,
    NOTEBOOK_SYS_PATH,
)
from mlmodels._metadata import SIGNATURE_FILE


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
    shared = {}
    for index, cell in enumerate(cells):
        text = _source(cell)
        if cell["cell_type"] == "code":
            try:
                tree = ast.parse(text)
            except SyntaxError:
                tree = ast.Module(body=[], type_ignores=[])
            scoped = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
            bound_here = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)}
            bound_here |= {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
            bound_here |= {node.arg for node in ast.walk(tree) if isinstance(node, ast.arg)}
            bound_here |= {(alias.asname or alias.name).split(".")[0] for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
            for name in sorted({node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)} - bound_here - set(dir(builtins))):
                if name in shared:
                    add("NB018", f"name [{name}] was bound in an earlier stage, pass it between stages in ws.params", index)
            pending: list[ast.AST] = [statement for statement in tree.body if not isinstance(statement, scoped + (ast.Import, ast.ImportFrom))]
            while pending:
                node = pending.pop()
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id != "ws":
                    shared.setdefault(node.id, index)
                pending.extend(child for child in ast.iter_child_nodes(node) if not isinstance(child, scoped))
            for line in text.split("\n"):
                if NOTEBOOK_MAGIC.match(line):
                    add("NB007", f"magic or shell line [{line.strip()}]", index)
                if NOTEBOOK_ABSOLUTE_PATH.search(line):
                    add("NB007", f"absolute path [{line.strip()}]", index)
                if NOTEBOOK_SECRET.search(line):
                    add("NB007", "possible secret in source", index)
            if NOTEBOOK_STAR_IMPORT.search(text):
                add("NB011", "import from mlmodels by name, never with *", index)
            if NOTEBOOK_PLOT.search(text) and not cell.get("metadata", {}).get("jupyter", {}).get("outputs_hidden"):
                add("NB016", "a cell that plots must collapse its output with the cell metadata [jupyter.outputs_hidden]", index)
            if NOTEBOOK_RENAME.search(text):
                add("NB017", "a name flows unaltered through every stage, add a column under its own name and never rename one", index)
            if NOTEBOOK_SYS_PATH.search(text):
                add("NB012", "the kernel puts mlmodels on the path, a notebook must not extend sys.path", index)
        elif any(row.startswith("|") and "**" in row for row in text.split("\n")):
            add("NB009", "bold in a table cell", index)
    data = _title_blocks(_title_text(cells))[0].get("Data", [])
    ignored_data = _ignored(notebook_dir, "data", "1000", "file.csv")
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
    stages = []
    for index, text in markdown:
        first = text.split("\n")[0]
        if first.startswith("### "):
            findings.append(("NB005", "headings deeper than level two are not allowed", index))
        elif first.startswith("## "):
            stage = first[3:].split(" (")[0].strip()
            stages.append(stage)
            if stage not in NOTEBOOK_STAGES:
                findings.append(("NB005", f"unknown stage [{stage}]", index))
            if stage in NOTEBOOK_STAGES and text != stage_heading(stage):
                findings.append(("NB006", f"stage [{stage}] must be only the heading [{stage_heading(stage)}]", index))
    known = [NOTEBOOK_STAGES.index(stage) for stage in stages if stage in NOTEBOOK_STAGES]
    if known != sorted(known):
        findings.append(("NB005", f"stages must be in the order {list(NOTEBOOK_STAGES)} found {stages}", None))
    if "Setup" not in stages:
        findings.append(("NB005", "stage [Setup] is required", None))
    stage_codes = {}
    current = None
    for index, cell in enumerate(cells):
        text = _source(cell)
        if cell["cell_type"] == "markdown" and text.startswith("## "):
            current = text[3:].split(" (")[0].strip()
            stage_codes[current] = 0
        elif cell["cell_type"] == "code" and current is not None:
            stage_codes[current] += 1
            if stage_codes[current] == 2:
                findings.append(("NB015", f"stage [{current}] must hold one code cell", index))
    setup = "\n".join(_source(cell) for cell in cells if cell["cell_type"] == "code")
    if not re.search(rf"""\bsetup_workspace\(\s*["']{re.escape(f"{module}/{model}/{name}")}["']""", setup):
        findings.append(("NB008", f"setup_workspace must be called with the workspace [{module}/{model}/{name}]", None))
    return findings


def stage_heading(stage):
    number = f"6.7.{NOTEBOOK_STAGES.index(stage) + 1}"
    return f"## {stage} ([{number}]({NOTEBOOK_SPEC}#{number.replace('.', '')}-{stage.lower().replace(' ', '-')}))"


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
