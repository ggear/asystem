#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

SCRIPT_FILE="tmp/scripts/media/downscale.sh"
if [ -n "${SHARE_DIR_MEDIA}" ]; then
  find . -name downscale.sh -exec "{}" \;
elif [ -n "${SHARE_DIR}" ]; then
  if [ -f "${SHARE_DIR}/${SCRIPT_FILE}" ]; then "${SHARE_DIR}/${SCRIPT_FILE}"; else "${ROOT_DIR}/lib/clean.sh" "${SHARE_DIR}"; fi
else
  for _SHARE_DIR in ${SHARE_DIRS_LOCAL}; do
    if [ -f "${_SHARE_DIR}/${SCRIPT_FILE}" ]; then "${_SHARE_DIR}/${SCRIPT_FILE}"; else "${ROOT_DIR}/lib/clean.sh" "${_SHARE_DIR}"; fi
  done
fi