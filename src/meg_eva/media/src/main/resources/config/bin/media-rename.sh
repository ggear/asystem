#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. "${ROOT_DIR}/.env_media"

if [ -n "${SHARE_DIR_MEDIA}" ]; then
  find . -name rename.sh -exec "{}" \;
elif [ -n "${SHARE_DIR}" ]; then
  "${SHARE_DIR}/tmp/script/rename.sh"
else
  for _SHARE_DIR in ${SHARE_DIRS_LOCAL}; do "${_SHARE_DIR}/tmp/scripts/rename.sh"; done
fi