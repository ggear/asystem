#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

SCRIPT_NAME="normalise.sh"
SCRIPT_PATH="${ROOT_DIR}/lib/${SCRIPT_NAME}"
SCRIPT_FILE="tmp/scripts/media/${SCRIPT_NAME}"
RESULT=0
if [ -n "${SHARE_DIR_MEDIA}" ]; then
  "${SCRIPT_PATH}" "${PWD}" || RESULT=1
elif [ -n "${SHARE_DIR}" ]; then
  mkdir -p "${SHARE_DIR}/${SCRIPT_FILE}/../.."
  chmod 777 "${SHARE_DIR}/${SCRIPT_FILE}/../.."
  if [ -f "${SHARE_DIR}/${SCRIPT_FILE}" ]; then "${SHARE_DIR}/${SCRIPT_FILE}" || RESULT=1; else "${SCRIPT_PATH}" "${SHARE_DIR}" || RESULT=1; fi
else
  for _SHARE_DIR in ${SHARE_DIRS_LOCAL}; do
    mkdir -p "${_SHARE_DIR}/${SCRIPT_FILE}/../.."
    chmod 777 "${_SHARE_DIR}/${SCRIPT_FILE}/../.."
    if [ -f "${_SHARE_DIR}/${SCRIPT_FILE}" ]; then "${_SHARE_DIR}/${SCRIPT_FILE}" || RESULT=1; else "${SCRIPT_PATH}" "${_SHARE_DIR}" || RESULT=1; fi
  done
fi
exit ${RESULT}
