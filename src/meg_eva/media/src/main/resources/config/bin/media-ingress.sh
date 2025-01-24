#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. "${ROOT_DIR}/.env_media"

[[ $(uname) == "Linux" ]] && "${ROOT_DIR}/lib/ingress.sh" /share/2
[[ $(uname) == "Linux" ]] && "${PYTHON_DIR}/python" "${LIB_ROOT}/ingress.py" /share/2/tmp
