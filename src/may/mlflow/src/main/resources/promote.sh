#!/bin/bash

set -o nounset
set -o errexit

ROOT_DIR="$(cd "$(dirname "$(readlink -f "$0")")/../../.." && pwd)"
PYENV_BIN="${HOME}/.pyenv/versions/asystem/bin"
NAME="${1:?usage: promote.sh <registered model> --gate <file> --reviewed-by <name> [--hosts python,rust,go] [--archs x86_64,aarch64]}"
shift

MLFLOW_TRACKING_URI="$(sed -n 's/^MLFLOW_TRACKING_URI=//p' "${ROOT_DIR}/.env_all")"
export MLFLOW_TRACKING_URI
export PYTHONPATH="${ROOT_DIR}/../../all/_/src/build/python${PYTHONPATH:+:${PYTHONPATH}}"
"${PYENV_BIN}/python" -W ignore -m asystem.model promote "${NAME}" --workspaces "${ROOT_DIR}/src/main/model" "$@"
