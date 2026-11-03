#!/bin/bash

set -o nounset
set -o errexit

ROOT_DIR="$(cd "$(dirname "$(readlink -f "$0")")/../../.." && pwd)"
PYENV_BIN="${HOME}/.pyenv/versions/asystem/bin"
KERNEL_PATH="${ROOT_DIR}/src/main/python:${ROOT_DIR}/../../all/_/src/build/python"
TARGET="${1:?usage: notebook.sh <module>/<model>/<notebook>, with REGISTER=1 to run the Register section}"
OUTPUT_DIR="${ROOT_DIR}/target/notebook/${TARGET}"

"${PYENV_BIN}/python" -m ipykernel install --user --name asystem --display-name "asystem (Python 3.12)" --env PYTHONPATH "${KERNEL_PATH}" >/dev/null
rm -rf "${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}/input"
"${PYENV_BIN}/python" - "${ROOT_DIR}/src/main/model/${TARGET}/notebook.ipynb" "${OUTPUT_DIR}/input/notebook.ipynb" "${REGISTER:-0}" <<'PYTHON'
import json
import sys

source, target, register = sys.argv[1:4]
with open(source) as source_file:
    notebook = json.load(source_file)
if register != "1":
    stop = next((index for index, cell in enumerate(notebook["cells"]) if cell["cell_type"] == "markdown" and "".join(cell["source"]).startswith("## Register")), len(notebook["cells"]))
    notebook["cells"] = notebook["cells"][:stop]
with open(target, "w") as target_file:
    json.dump(notebook, target_file)
PYTHON
cd "${ROOT_DIR}/src/main/model/${TARGET}"
"${PYENV_BIN}/jupyter" nbconvert --to notebook --execute --ExecutePreprocessor.kernel_name=asystem --ExecutePreprocessor.timeout=1800 \
  --output-dir "${OUTPUT_DIR}" "${OUTPUT_DIR}/input/notebook.ipynb"
