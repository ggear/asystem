#!/bin/bash

set -o nounset
set -o errexit

ROOT_DIR="$(cd "$(dirname "$(readlink -f "$0")")/../../.." && pwd)"
PYENV_BIN="${HOME}/.pyenv/versions/asystem/bin"
KERNEL_PATH="${ROOT_DIR}/src/main/python:${ROOT_DIR}/../../all/_/src/build/python"
TARGET="${1:?usage: notebook.sh <module>/<model>/<notebook>}"

"${PYENV_BIN}/python" -m ipykernel install --user --name asystem --display-name "asystem (Python 3.12)" --env PYTHONPATH "${KERNEL_PATH}" >/dev/null
mkdir -p "${ROOT_DIR}/target/notebook/${TARGET}"
cd "${ROOT_DIR}/src/main/model/${TARGET}"
"${PYENV_BIN}/jupyter" nbconvert --to notebook --execute --ExecutePreprocessor.kernel_name=asystem --ExecutePreprocessor.timeout=1800 \
  --output-dir "${ROOT_DIR}/target/notebook/${TARGET}" notebook.ipynb
