#!/bin/bash

. ../../../generate.sh

. ./.env

VERSION=${TASMOTA_FIRMWARE_VERSION}
pull_repo $(pwd) tasmota tasmota-core arendst/tasmota v${VERSION} ${1}
if [ ! -f src/build/resources/firmware/tasmota-${VERSION}.bin.gz ] || [ ! -f src/build/resources/firmware/tasmota-minimal-${VERSION}.bin.gz ]; then
  mkdir -p src/build/resources/firmware &&
    rm -rf src/build/resources/firmware/*.gz &&
    wget -O src/build/resources/firmware/tasmota-${VERSION}.bin.gz http://ota.tasmota.com/tasmota/release-${VERSION}/tasmota.bin.gz &&
    wget -O src/build/resources/firmware/tasmota-minimal-${VERSION}.bin.gz http://ota.tasmota.com/tasmota/release-${VERSION}/tasmota-minimal.bin.gz
fi
