#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

if [ -n "${SHARE_DIR_MEDIA}" ]; then
  "${ROOT_DIR}/lib/clean.sh" "${PWD}"
  "${PYTHON_DIR}/python" "${LIB_ROOT}/analyse.py" "${PWD}" "${MEDIA_GOOGLE_SHEET_GUID}" --verbose
elif [ -n "${SHARE_DIR}" ]; then
  if [ -f "${SHARE_DIR}/tmp/scripts/media/analyse.sh" ]; then
    "${SHARE_DIR}/tmp/scripts/media/analyse.sh"
  else
    "${PYTHON_DIR}/python" "${LIB_ROOT}/analyse.py" "${SHARE_DIR}/media" "${MEDIA_GOOGLE_SHEET_GUID}" --verbose
  fi
else
  for _SHARE_DIR in ${SHARE_DIRS_LOCAL}; do
    if [ -f "${_SHARE_DIR}/tmp/scripts/media/analyse.sh" ]; then
      "${_SHARE_DIR}/tmp/scripts/media/analyse.sh"
    else
      "${PYTHON_DIR}/python" "${LIB_ROOT}/analyse.py" "${_SHARE_DIR}" "${MEDIA_GOOGLE_SHEET_GUID}"
    fi
  done
fi
