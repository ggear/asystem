#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. "${ROOT_DIR}/../.env_media"

WORKING_DIR=${1}
if [ ! -d "${WORKING_DIR}" ]; then
  echo "Usage: ${0} <working-dir>"
  exit 1
fi

LOG="/tmp/asystem-media-clean.log"

echo -n "Cleaning '${WORKING_DIR}' ... "
rm -rf ${LOG}
find "${WORKING_DIR}" -name "merge.sh" -type f -delete &>${LOG}
find "${WORKING_DIR}" -name "reformat.sh" -type f -delete &>${LOG}
find "${WORKING_DIR}" -name "transcode.sh" -type f -delete &>${LOG}
find "${WORKING_DIR}" -name "._metadata_*.yaml" -type f -delete &>${LOG}
find "${WORKING_DIR}" -name "._transcode_*" -type d -exec rm -rf '{}' + &>${LOG}
if [ $(cat ${LOG} | wc -l) -gt 0 ]; then
  echo "failed"
  cat ${LOG}
else
  echo "done"
fi
