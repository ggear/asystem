#!/bin/bash

set -o nounset
set -o errexit

export MLFLOW_DISABLE_TELEMETRY=true
export MLFLOW_DISABLE_AGENT_HINT=1
ROOT_DIR="$(cd "$(dirname "$(readlink -f "$0")")/../../.." && pwd)"
PYENV_BIN="${HOME}/.pyenv/versions/asystem/bin"
KERNEL_PATH="${ROOT_DIR}/src/main/python:${ROOT_DIR}/../../all/_/src/build/python"
if [[ "${1:-}" == "new" ]]; then
  SCAFFOLD="${2:?usage: notebook.sh new <module>/<model>/<notebook> <static|wasm|onnx|pyfunc> [--local]}"
  FLAVOUR="${3:?usage: notebook.sh new <module>/<model>/<notebook> <static|wasm|onnx|pyfunc> [--local]}"
  IFS=/ read -r SCAFFOLD_MODULE SCAFFOLD_MODEL SCAFFOLD_NOTEBOOK <<<"${SCAFFOLD}"
  PYTHONPATH="${ROOT_DIR}/src/main/python" "${PYENV_BIN}/python" -m mlmodels notebook new "${SCAFFOLD_MODULE}" "${SCAFFOLD_MODEL}" "${SCAFFOLD_NOTEBOOK}" "${FLAVOUR}" --root "${ROOT_DIR}/src/main/notebook" ${4:+"$4"}
  exit 0
fi
TARGET="${1:?usage: notebook.sh <module>/<model>/<notebook> [--register], or notebook.sh new <module>/<model>/<notebook> <flavour>}"
[[ "${2:-}" == "--register" ]] && REGISTER=1
OUTPUT_DIR="${ROOT_DIR}/target/notebook/${TARGET}"

"${PYENV_BIN}/python" -m ipykernel install --user --name asystem --display-name "asystem (Python 3.12)" --env PYTHONPATH "${KERNEL_PATH}" >/dev/null
rm -rf "${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}"
PYTHONPATH="${ROOT_DIR}/src/main/python" "${PYENV_BIN}/python" -W ignore -m mlmodels run "${ROOT_DIR}/src/main/notebook/${TARGET}" "${OUTPUT_DIR}" "${REGISTER:-0}" "${ROOT_DIR}/../../../.py_deps_prod.txt" "${ROOT_DIR}/../.."
