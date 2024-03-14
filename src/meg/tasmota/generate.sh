#!/bin/bash

. ../../../generate.sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

. ${ROOT_DIR}/.env

VERSION=${TASMOTA_FIRMWARE_VERSION}
pull_repo $(pwd) tasmota tasmota-core arendst/tasmota v${VERSION} ${1}
if [ ! -f ${ROOT_DIR}/src/build/resources/firmware/tasmota-${VERSION}.bin.gz ] || [ ! -f ${ROOT_DIR}/src/build/resources/firmware/tasmota-minimal-${VERSION}.bin.gz ] || [ ! -f ${ROOT_DIR}/src/build/resources/firmware/tasmota32-${VERSION}.bin ]; then
  mkdir -p ${ROOT_DIR}/src/build/resources/firmware &&
    rm -rf ${ROOT_DIR}/src/build/resources/firmware/*.gz &&
    wget -q -O ${ROOT_DIR}/src/build/resources/firmware/tasmota-${VERSION}.bin.gz http://ota.tasmota.com/tasmota/release-${VERSION}/tasmota.bin.gz &&
    wget -q -O ${ROOT_DIR}/src/build/resources/firmware/tasmota-minimal-${VERSION}.bin.gz http://ota.tasmota.com/tasmota/release-${VERSION}/tasmota-minimal.bin.gz &&
    wget -q -O ${ROOT_DIR}/src/build/resources/firmware/tasmota32-${VERSION}.bin http://ota.tasmota.com/tasmota32/release/tasmota32.bin
fi
