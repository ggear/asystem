#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. "${ROOT_DIR}/.env_media"

SHARE_DIRS_SPACE=${SHARE_DIRS_LOCAL}
if [ -n "${SHARE_DIR_MEDIA}" ]; then
  SHARE_DIRS_SPACE="${SHARE_DIR_MEDIA}"
elif [ -n "${SHARE_DIR}" ]; then
  SHARE_DIRS_SPACE="${SHARE_DIR}"
fi
$(echo $([[ $(uname) == "Darwin" ]] && echo "g")"df") -h --output=target,size,used,avail,pcent ${SHARE_DIRS_SPACE}
