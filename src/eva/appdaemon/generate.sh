#!/bin/bash

. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

HOST="$(grep "$(basename "$(dirname "${ROOT_DIR}")")" "${ROOT_DIR}/../../../.hosts" | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')"-"$(basename "$(dirname "${ROOT_DIR}")")"
HOST_LETSENCRYPT="$(grep $(basename $(dirname $(find ${ROOT_DIR}/../../.. -type d -mindepth 3 -maxdepth 3 -name letsencrypt))) ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-$(basename $(dirname $(find ${ROOT_DIR}/../../.. -type d -mindepth 3 -maxdepth 3 -name letsencrypt)))"

"${ROOT_DIR}/src/main/resources/image/certificates.sh" pull "${HOST_LETSENCRYPT}" "${HOST}"

rm -rf "${ROOT_DIR}/src/main/resources/data/apps/"*.py
for PY_FILE in "${ROOT_DIR}/src/main/python/appdaemon/"*.py; do
  PY_PATH="${ROOT_DIR}/src/main/resources/data/apps/$(basename "${PY_FILE}")"
  echo -e "\"\"\"\nWARNING: This file is written by the build process, any manual edits will be lost!\n\"\"\"\n" >"${PY_PATH}"
  cat "${PY_FILE}" >>"${PY_PATH}"
done
