#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

MEDIA_FILE_DIR=""
if [ -n "${SHARE_DIR_MEDIA}" ]; then
  if [ "$(basename "$(dirname "$(pwd)")")" == "movies" ] ||
    [ "$(basename "$(dirname "$(pwd)")")" == "series" ] ||
    [ "$(basename "$(dirname "$(dirname "$(pwd)")")")" == "series" ]; then
    MEDIA_FILE_DIR="${PWD}"
  fi
fi
if [ -n "${MEDIA_FILE_DIR}" ]; then
  asystem-media-clean
  "${PYTHON_DIR}/python" "${LIB_ROOT}/analyse.py" --verbose --force "${MEDIA_FILE_DIR}" "${MEDIA_GOOGLE_SHEET_GUID}"
else
  echo "" && echo "Error: Not in media file root directory, not doing anything!" && echo ""
fi
