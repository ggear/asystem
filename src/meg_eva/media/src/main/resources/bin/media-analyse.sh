#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

SCRIPT_NAME="analyse.sh"
SCRIPT_PATH="${LIB_ROOT}/${SCRIPT_NAME}"
SCRIPT_FILE="tmp/scripts/media/${SCRIPT_NAME}"
if [ -n "${SHARE_DIR_MEDIA}" ]; then
  "${ROOT_DIR}/lib/clean.sh" "${PWD}"
  "${PYTHON_DIR}/python" "${SCRIPT_PATH}" "${PWD}" "${MEDIA_GOOGLE_SHEET_GUID}" --verbose
elif [ -n "${SHARE_DIR}" ]; then
  if [ -f "${SHARE_DIR}/${SCRIPT_FILE}" ]; then "${SHARE_DIR}/${SCRIPT_FILE}"; else "${PYTHON_DIR}/python" "${SCRIPT_PATH}" "${SHARE_DIR}/media" "${MEDIA_GOOGLE_SHEET_GUID}" --verbose; fi
else
  for _SHARE_DIR in ${SHARE_DIRS_LOCAL}; do
    if [ -f "${_SHARE_DIR}/${SCRIPT_FILE}" ]; then "${_SHARE_DIR}/${SCRIPT_FILE}" "${_SHARE_DIR}"; else "${PYTHON_DIR}/python" "${SCRIPT_PATH}" "${_SHARE_DIR}" "${MEDIA_GOOGLE_SHEET_GUID}"; fi
  done
fi
