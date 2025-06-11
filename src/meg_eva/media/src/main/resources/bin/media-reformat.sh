#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

SCRIPT_NAME="reformat.sh"
SCRIPT_PATH="${ROOT_DIR}/lib/${SCRIPT_NAME}"
SCRIPT_FILE="tmp/scripts/media/${SCRIPT_NAME}"
if [ -n "${SHARE_DIR_MEDIA}" ]; then
  find . -name ${SCRIPT_NAME} -exec "{}" \; | grep -v "No such file or directory"
elif [ -n "${SHARE_DIR}" ]; then
  [[ ! -f "${SHARE_DIR}/${SCRIPT_FILE}" ]] && asystem-media-analyse
  "${SHARE_DIR}/${SCRIPT_FILE}"
else
  for _SHARE_DIR in ${SHARE_DIRS_LOCAL}; do
    [[ ! -f "${SHARE_DIR}/${SCRIPT_FILE}" ]] && asystem-media-"${SCRIPT_NAME%.sh}"
    "${_SHARE_DIR}/${SCRIPT_FILE}"
  done
fi
