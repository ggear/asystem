#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. "${ROOT_DIR}/.env"

if [ -n "${SHARE_DIR_MEDIA}" ]; then
  find . -name transcode.sh -exec "{}" +
elif [ -n "${SHARE_DIR}" ]; then
  "${SHARE_DIR}/tmp/script/transcode.sh"
else
  for SHARE_DIRS_ITEM in ${SHARE_DIRS}; do "${SHARE_DIRS_ITEM}/tmp/scripts/transcode.sh"; done
fi