#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

SCRIPT_NAME="refresh"
SCRIPT_PATH="${LIB_ROOT}/${SCRIPT_NAME}.py"
RESULT=0
export SABNZBD_URL SABNZBD_API_KEY
export SONARR_URL SONARR_API_KEY
export PLEX_URL PLEX_TOKEN
"${PYTHON_DIR}/python" "${SCRIPT_PATH}" "${SHARE_ROOT}" || RESULT=$?
exit ${RESULT}
