#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. "${ROOT_DIR}/.env"

if [ -n "${SHARE_DIR_MEDIA}" ]; then
  "${ROOT_DIR}/lib/clean.sh" "${PWD}"
elif [ -n "${SHARE_DIR}" ]; then
  "${ROOT_DIR}/lib/clean.sh" "${SHARE_DIR}"
else
  for SHARE_DIRS_ITEM in ${SHARE_DIRS}; do "${ROOT_DIR}/lib/clean.sh" "${SHARE_DIRS_ITEM}"; done
  "${PYTHON_DIR}/python" "${ROOT_DIR}/lib/analyse.py" "/share" "14W6B2404_e1JKftOvHE4moV5w6VP5aitHVpX3Qcgcl8" --clean
fi
