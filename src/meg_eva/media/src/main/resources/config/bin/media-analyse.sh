#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. "${ROOT_DIR}/.env_media"

SHEET_GUID="14W6B2404_e1JKftOvHE4moV5w6VP5aitHVpX3Qcgcl8"

if [ -n "${SHARE_DIR_MEDIA}" ]; then
  "${ROOT_DIR}/lib/clean.sh" "${PWD}"
  "${PYTHON_DIR}/python" "${ROOT_DIR}/lib/analyse.py" "${PWD}" "${SHEET_GUID}" --verbose
elif [ -n "${SHARE_DIR}" ]; then
  "${PYTHON_DIR}/python" "${ROOT_DIR}/lib/analyse.py" "${SHARE_DIR}" "${SHEET_GUID}"
else
  for _SHARE_DIR in ${SHARE_DIRS_LOCAL}; do "${PYTHON_DIR}/python" "${ROOT_DIR}/lib/analyse.py" "${_SHARE_DIR}" "${SHEET_GUID}"; done
fi
