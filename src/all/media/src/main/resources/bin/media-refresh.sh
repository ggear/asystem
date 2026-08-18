#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

SCRIPT_NAME="refresh"
SCRIPT_PATH="${LIB_ROOT}/${SCRIPT_NAME}.py"
RESULT=0
echo "Refreshing 'http://${PLEX_SERVICE_PROD}:${PLEX_HTTP_PORT}/libraries' ... "
"${PYTHON_DIR}/python" "${SCRIPT_PATH}" \
  "http://${PLEX_SERVICE_PROD}:${PLEX_HTTP_PORT}" "${PLEX_TOKEN}" "${SHARE_ROOT}" || RESULT=1
if [ ${RESULT} -ne 0 ]; then
  echo "failed"
  exit 1
fi
echo "done"
exit ${RESULT}
