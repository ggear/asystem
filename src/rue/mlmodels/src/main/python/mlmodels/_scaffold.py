import json
import os
from os.path import isfile, join

from mlmodels._constants import PROJECT_FLAVOURS
from mlmodels._document import write_json
from mlmodels._lint_notebook import stage_heading
from mlmodels._metadata import SIGNATURE_FILE
from mlmodels._signature import build_signature, check_name, registered_name, signature_input, signature_output


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
    os.makedirs(join(notebook_dir, "data"), exist_ok=True)
    created = [notebook_path, join(notebook_dir, SIGNATURE_FILE)]
    keep = join(notebook_dir, "data", ".gitkeep")
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


def _scaffold_notebook(module, model, notebook, name, flavour, local):
    def markdown(text):
        return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)}

    def code(text):
        return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": text.strip("\n").splitlines(keepends=True)}

    def stage(title):
        return markdown(stage_heading(title))

    static = flavour == "static"
    target = '{"kind": "local"}' if local else '{"kind": "served"}'
    cells = [
        markdown(
            f"# {module} / {model} / {notebook}\n\n**Intent**\n- Estimates `{model}_out` from `{model}_in`, and must:\n  - State what the output is intended to be and what it must achieve.\n\n"
            "**Data**\n- `golden` is the fixed samples and expected outputs.\n\n**Status**\n- Scaffolded, so the intent, the signature and the data are still to be written."
        ),
        stage("Setup"),
        code(f'from mlmodels import setup_workspace\n\nws = setup_workspace("{module}/{model}/{notebook}")\n'),
    ]
    if not static:
        cells += [stage("Collect"), stage("Prepare"), stage("Explore"), stage("Train")]
    cells += [stage("Define")]
    if static:
        cells += [code('from mlmodels import define_model\n\nCONSTANTS = {ws.outputs[0]: 1}\ndefine_model(ws, model=1000, flavour="static", source=CONSTANTS, label="scaffold constants")\n')]
    else:
        cells += [stage("Evaluate")]
    cells += [
        stage("Package"),
        code(
            f'from mlmodels import package_model\n\npackage_model(ws, 1000, {{ws.inputs[0]: [1.0, None], "expect": ["ok", "error"]}}, target={target})\n'
            if static
            else 'print("no model is defined yet, so nothing is packaged")\n'
        ),
        stage("Register"),
        code("from mlmodels import register_model\n\nregister_model(ws, 1000)" if static else 'print("no model is defined yet, so nothing is registered")'),
    ]
    if local:
        cells = cells[:-2]
    return {
        "cells": cells,
        "metadata": {"kernelspec": {"name": "asystem", "language": "python", "display_name": "asystem (Python 3.12)"}, "language_info": {"name": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
