import json
import logging
import re
import sys
from contextlib import ExitStack
from os.path import isfile, join

import nbformat
from nbclient import NotebookClient

from asystem.errors import GateError
from asystem.metadata import PROJECT_DIR, lint_metadata
from asystem.model import PROJECT_MANIFEST
from asystem.report import stage, subject

KERNEL = "asystem"
CELL_TIMEOUT = 1800
SECTION = re.compile(r"^## (.+)$", re.MULTILINE)
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def run_notebook(workspace_dir, output_dir, register, pins_path, source_dir):
    target = "/".join(workspace_dir.rstrip("/").split("/")[-3:])
    notebook = nbformat.read(join(workspace_dir, "notebook.ipynb"), as_version=4)
    if not register:
        stop = next((index for index, cell in enumerate(notebook.cells) if cell.cell_type == "markdown" and cell.source.startswith("## Register")), len(notebook.cells))
        notebook.cells = notebook.cells[:stop]
    client = NotebookClient(notebook, kernel_name=KERNEL, timeout=CELL_TIMEOUT, resources={"metadata": {"path": workspace_dir}}, extra_arguments=["--IPKernelApp.log_level=ERROR"])
    with subject(f"notebook {target}"):
        try:
            with ExitStack() as stages, client.setup_kernel():
                for index, cell in enumerate(notebook.cells):
                    heading = SECTION.match(cell.source) if cell.cell_type == "markdown" else None
                    if heading:
                        stages.close()
                        stages.enter_context(stage(heading.group(1).lower()))
                    elif cell.cell_type == "code":
                        client.execute_cell(cell, index)
        finally:
            nbformat.write(notebook, join(output_dir, "notebook.ipynb"))
        if isfile(join(workspace_dir, PROJECT_DIR, PROJECT_MANIFEST)):
            with stage("metadata") as entry:
                with open(join(workspace_dir, PROJECT_DIR, PROJECT_MANIFEST)) as manifest_file:
                    flavour = json.load(manifest_file)["flavour"]
                findings = lint_metadata(workspace_dir, flavour, pins_path, source_dir)
                if findings:
                    raise GateError("Metadata", "check", "; ".join(f"{rule} {message}" for rule, message in findings))
                entry.detail = flavour


def main(arguments=None):
    logging.getLogger("IPKernelApp").setLevel(logging.ERROR)
    arguments = sys.argv[1:] if arguments is None else arguments
    if len(arguments) != 5:
        print("ERROR usage runner <workspace dir> <output dir> <register 0|1> <pins path> <source dir>", file=sys.stderr)
        return 2
    workspace_dir, output_dir, register, pins_path, source_dir = arguments
    try:
        run_notebook(workspace_dir, output_dir, register == "1", pins_path, source_dir)
    except Exception as error:
        print(f"ERROR {ANSI.sub('', str(error))}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
