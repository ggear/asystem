#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. "${ROOT_DIR}/.env_media"

# TODO: Account for being in more specific directory
for SHARE_DIR_ITEM in ${SHARE_DIRS}; do "${PYTHON_DIR}/python" "${ROOT_DIR}/lib/rename.py" "${SHARE_DIR_ITEM}/tmp"; done
