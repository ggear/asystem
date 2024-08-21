#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. "${ROOT_DIR}/.env_media"

if [ -n "${SHARE_DIR_MEDIA}" ]; then
  "${ROOT_DIR}/lib/clean.sh" "${PWD}"
  "${PYTHON_DIR}/python" "${ROOT_DIR}/lib/analyse.py" "${PWD}" "${MEDIA_GOOGLE_SHEET_GUID}" --verbose
elif [ -n "${SHARE_DIR}" ]; then
  "${PYTHON_DIR}/python" "${ROOT_DIR}/lib/analyse.py" "${SHARE_DIR}/media" "${MEDIA_GOOGLE_SHEET_GUID}" --verbose
else
  for _SHARE_DIR in ${SHARE_DIRS_LOCAL}; do "${PYTHON_DIR}/python" "${ROOT_DIR}/lib/analyse.py" "${_SHARE_DIR}" "${MEDIA_GOOGLE_SHEET_GUID}"; done
fi
