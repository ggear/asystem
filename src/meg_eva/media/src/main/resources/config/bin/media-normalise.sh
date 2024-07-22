#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. "${ROOT_DIR}/.env"

if [ -n "${SHARE_DIR_MEDIA}" ]; then
  "${ROOT_DIR}/lib/normalise.sh" "${PWD}"
elif [ -n "${SHARE_DIR}" ]; then
  "${ROOT_DIR}/lib/normalise.sh" "${SHARE_DIR}"
else
  for SHARE_DIRS_ITEM in ${SHARE_DIRS}; do "${ROOT_DIR}/lib/normalise.sh" "${SHARE_DIRS_ITEM}"; done
fi
