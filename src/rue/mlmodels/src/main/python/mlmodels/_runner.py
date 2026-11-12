import json
import os
import re
import tempfile
from contextlib import ExitStack
from os.path import isfile, join

import nbformat
from nbclient import NotebookClient

from asystem.report import stage, subject
from mlmodels._constants import PROJECT_MANIFEST
from mlmodels._detail import DETAIL_ENV, take_detail
from mlmodels._errors import GateError
from mlmodels._metadata import PROJECT_DIR, lint_metadata, requirements

KERNEL = "asystem"


CELL_TIMEOUT = 1800


STAGE = re.compile(r"^## (.+)$", re.MULTILINE)


ANSI = re.compile(r"\x1b\[[0-9;]*m")


def run_notebook(workspace_dir, output_dir, register, pins_path, source_dir):
    target = "/".join(workspace_dir.rstrip("/").split("/")[-3:])
    notebook = nbformat.read(join(workspace_dir, "notebook.ipynb"), as_version=4)
    if not register:
        stop = next((index for index, cell in enumerate(notebook.cells) if cell.cell_type == "markdown" and cell.source.startswith("## Register")), len(notebook.cells))
        notebook.cells = notebook.cells[:stop]
    client = NotebookClient(notebook, kernel_name=KERNEL, timeout=CELL_TIMEOUT, resources={"metadata": {"path": workspace_dir}}, extra_arguments=["--IPKernelApp.log_level=ERROR"])
    detail_path = join(tempfile.mkdtemp(), "stage-detail")
    current = {"entry": None, "cells": 0}

    def settle():
        if current["entry"] is not None:
            cells = current["cells"]
            current["entry"].detail = take_detail(detail_path) or f"{cells} cell{'' if cells == 1 else 's'}"

    with subject(f"notebook {target}"):
        os.environ[DETAIL_ENV] = detail_path
        try:
            with ExitStack() as stages, client.setup_kernel():
                for index, cell in enumerate(notebook.cells):
                    heading = STAGE.match(cell.source) if cell.cell_type == "markdown" else None
                    if heading:
                        settle()
                        stages.close()
                        current.update(entry=stages.enter_context(stage(heading.group(1).split(" (")[0].lower())), cells=0)
                    elif cell.cell_type == "code":
                        client.execute_cell(cell, index)
                        current["cells"] += 1
                settle()
        finally:
            os.environ.pop(DETAIL_ENV, None)
            nbformat.write(notebook, join(output_dir, "notebook.ipynb"))
        if isfile(join(workspace_dir, PROJECT_DIR, PROJECT_MANIFEST)):
            with open(join(workspace_dir, PROJECT_DIR, PROJECT_MANIFEST)) as manifest_file:
                flavour = json.load(manifest_file)["flavour"]
            with stage("requirements") as entry:
                to_add, summary, lines = requirements(workspace_dir, flavour, pins_path, source_dir)
                entry.detail = f"{to_add} to add" + (f": {summary}" if summary else "")
            for line in lines:
                print(f"    {line}", flush=True)
            with stage("metadata") as entry:
                findings = lint_metadata(workspace_dir, flavour, pins_path)
                if findings:
                    raise GateError("Metadata", "check", "; ".join(f"{rule} {message}" for rule, message in findings))
                entry.detail = flavour
