#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/../.env_media"

WORKING_DIR=${1}
if [ ! -d "${WORKING_DIR}" ]; then
  echo "Usage: ${0} <working-dir>"
  exit 1
fi

LOG="/tmp/media-clean.log"

echo -n "Cleaning '${WORKING_DIR}' ... "
rm -f "${LOG}"
${FIND_CMD} "${WORKING_DIR}" -name ".DS_Store" -type f -delete >>"${LOG}" 2>&1
${FIND_CMD} "${WORKING_DIR}" -name "._metadata_*.yaml" -type f -delete >>"${LOG}" 2>&1
${FIND_CMD} "${WORKING_DIR}" -name "._defaults_analysed_*.yaml" -type f -delete >>"${LOG}" 2>&1
for SCRIPT in "rename" "check" "merge" "upscale" "reformat" "transcode" "downscale"; do
  ${FIND_CMD} "${WORKING_DIR}" -name "${SCRIPT}.sh" -type f -delete >>"${LOG}" 2>&1
  ${FIND_CMD} "${WORKING_DIR}" -name "._${SCRIPT}_*" -type d -exec rm -rf '{}' + >>"${LOG}" 2>&1
done
[ -d "${WORKING_DIR}" ] && ${FIND_CMD} "${WORKING_DIR}" -path "*/share/*/media/*" -type d -empty -delete >>"${LOG}" 2>&1
[ -d "${WORKING_DIR}" ] && ${FIND_CMD} "${WORKING_DIR}" -path "*/share/*/media/*" -type d -empty -delete >>"${LOG}" 2>&1
if [ -s "${LOG}" ]; then
  echo "failed"
  cat "${LOG}"
  exit 1
fi
echo "done"
exit 0
