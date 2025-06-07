#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

[[ $(uname) == "Linux" ]] && "${ROOT_DIR}/lib/ingress.sh" /share/3
[[ $(uname) == "Linux" ]] && "${PYTHON_DIR}/python" "${LIB_ROOT}/ingress.py" /share/3/tmp
