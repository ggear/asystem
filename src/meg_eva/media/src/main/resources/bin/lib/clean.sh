#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/../.env_media"

WORKING_DIR=${1}
if [ ! -d "${WORKING_DIR}" ]; then
  echo "Usage: ${0} <working-dir>"
  exit 1
fi

LOG="/tmp/asystem-media-clean.log"

echo -n "Cleaning '${WORKING_DIR}' ... "
rm -rf ${LOG}
find "${WORKING_DIR}" -name ".DS_Store" -type f -delete &>${LOG}
find "${WORKING_DIR}" -name "._metadata_*.yaml" -type f -delete &>${LOG}
find "${WORKING_DIR}" -name "._defaults_analysed_*.yaml" -type f -delete &>${LOG}
for SCRIPT in "rename" "check" "merge" "upscale" "reformat" "transcode" "downscale"; do
  find "${WORKING_DIR}" -name "${SCRIPT}.sh" -type f -delete &>${LOG}
  find "${WORKING_DIR}" -name "._${SCRIPT}_*" -type d -exec rm -rf '{}' + &>${LOG}
done
find "${WORKING_DIR}" -path "*/share/*/media/*" -type d -empty -delete &>${LOG}
find "${WORKING_DIR}" -path "*/share/*/media/*" -type d -empty -delete &>${LOG}
if [ $(cat ${LOG} | wc -l) -gt 0 ]; then
  echo "failed"
  cat ${LOG}
else
  echo "done"
fi
