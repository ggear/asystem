#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

SCRIPT_NAME="refresh.sh"
SCRIPT_PATH="${ROOT_DIR}/lib/${SCRIPT_NAME}"
SCRIPT_FILE="tmp/scripts/media/${SCRIPT_NAME}"
if [ -n "${SHARE_DIR_MEDIA}" ]; then
  [[ "${SHARE_DIR}" == */share/3 ]] && "${SCRIPT_PATH}" sonarr
elif [ -n "${SHARE_DIR}" ]; then
  [[ "${SHARE_DIR}" == */share/3 ]] && "${SCRIPT_PATH}" sonarr
else
  "${SCRIPT_PATH}" sonarr
fi
