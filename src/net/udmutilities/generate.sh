#!/bin/bash

. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

HOST="$(grep "$(basename "$(dirname "${ROOT_DIR}")")" "${ROOT_DIR}/../../../.hosts" | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')"-"$(basename "$(dirname "${ROOT_DIR}")")"
HOST_LETSENCRYPT="$(grep $(basename $(dirname $(find ${ROOT_DIR}/../../.. -type d -mindepth 3 -maxdepth 3 -name letsencrypt))) ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-$(basename $(dirname $(find ${ROOT_DIR}/../../.. -type d -mindepth 3 -maxdepth 3 -name letsencrypt)))"

"${ROOT_DIR}/src/main/resources/image/udm-certificates/certificates.sh" pull "${HOST_LETSENCRYPT}" "${HOST}"

VERSION=ggear-patch-1
pull_repo "${ROOT_DIR}" "${1}" "udmutilities" "udm-utilities" "ggear/udm-utilities" "${VERSION}"
rm -rf "${ROOT_DIR}/src/main/resources/image/udm-utilities"
mkdir -p "${ROOT_DIR}/src/main/resources/image/udm-utilities"
cp -rvf "${ROOT_DIR}/../../../.deps/udmutilities/udm-utilities/on-boot-script" "${ROOT_DIR}/src/main/resources/image/udm-utilities"
