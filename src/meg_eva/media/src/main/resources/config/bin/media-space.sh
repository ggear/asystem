#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. "${ROOT_DIR}/.env"

SHARE_DIRS_LOCAL=${SHARE_DIRS}
SHARE_DIRS_LOCAL_LABEL=/share
if [ -n "${SHARE_DIR_MEDIA}" ]; then
  SHARE_DIRS_LOCAL=${SHARE_DIR_MEDIA}
  SHARE_DIRS_LOCAL_LABEL=$(dirname ${SHARE_DIR_MEDIA})
elif [ -n "${SHARE_DIR}" ]; then
  SHARE_DIRS_LOCAL=${SHARE_DIR}
  SHARE_DIRS_LOCAL_LABEL=${SHARE_DIR}
fi
echo "Space '${SHARE_DIRS_LOCAL_LABEL}' ... done"
df -h $(echo ${SHARE_DIRS_LOCAL} | tr '\n' ' ') | cut -c 40-
