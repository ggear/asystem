#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. "${ROOT_DIR}/.env"

SHARE_DIR=${1}
if [ ! -d "${SHARE_DIR}" ]; then
  echo "Usage: ${0} <share-dir>"
  exit 1
fi

echo -n "Cleaning ${SHARE_DIR} ... "
find "${SHARE_DIR}" -name "merge.sh" -type f -delete
find "${SHARE_DIR}" -name "reformat.sh" -type f -delete
find "${SHARE_DIR}" -name "transcode.sh" -type f -delete
find "${SHARE_DIR}" -name "._metadata_*.yaml" -type f -delete
find "${SHARE_DIR}" -name "._transcode_*" -type d -exec rmdir "{}" +
echo "done"
