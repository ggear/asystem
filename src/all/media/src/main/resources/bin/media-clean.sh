#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

SCRIPT_NAME="clean.sh"
SCRIPT_PATH="${ROOT_DIR}/lib/${SCRIPT_NAME}"
SCRIPT_FILE="tmp/scripts/media/${SCRIPT_NAME}"
if [ -n "${SHARE_DIR_MEDIA}" ]; then
  "${SCRIPT_PATH}" "${PWD}"
elif [ -n "${SHARE_DIR}" ]; then
  if [ -f "${SHARE_DIR}/${SCRIPT_FILE}" ]; then "${SHARE_DIR}/${SCRIPT_FILE}"; else "${SCRIPT_PATH}" "${SHARE_DIR}"; fi
else
  for _SHARE_DIR in ${SHARE_DIRS_LOCAL}; do
    if [ -f "${_SHARE_DIR}/${SCRIPT_FILE}" ]; then "${_SHARE_DIR}/${SCRIPT_FILE}"; else "${SCRIPT_PATH}" "${_SHARE_DIR}"; fi
  done
fi
