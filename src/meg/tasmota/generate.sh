#!/bin/bash

. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env"

# NOTES: https://github.com/arendst/Tasmota/releases
# DEFINED: [/asystem/src/meg/tasmota/.env_all](https://github.com/ggear/asystem/blob/master/src/meg/tasmota/.env_all)
VERSION=${TASMOTA_FIRMWARE_VERSION}
pull_repo "${ROOT_DIR}" "${1}" "tasmota" "tasmota-core" "arendst/tasmota" "v${VERSION}" || exit $?
if [ ! -s "${ROOT_DIR}/src/build/resources/firmware/tasmota-${VERSION}.bin.gz" ] || [ ! -s "${ROOT_DIR}/src/build/resources/firmware/tasmota-lite-${VERSION}.bin.gz" ] || [ ! -s "${ROOT_DIR}/src/build/resources/firmware/tasmota-minimal-${VERSION}.bin.gz" ] || [ ! -s "${ROOT_DIR}/src/build/resources/firmware/tasmota32-${VERSION}.bin" ]; then
  if ! { mkdir -p "${ROOT_DIR}/src/build/resources/firmware" &&
    rm -rf "${ROOT_DIR}/src/build/resources/firmware/"*.gz "${ROOT_DIR}/src/build/resources/firmware/"*.bin &&
    wget -q -O "${ROOT_DIR}/src/build/resources/firmware/tasmota-${VERSION}.bin.gz" "http://ota.tasmota.com/tasmota/release-${VERSION}/tasmota.bin.gz" &&
    wget -q -O "${ROOT_DIR}/src/build/resources/firmware/tasmota-lite-${VERSION}.bin.gz" "http://ota.tasmota.com/tasmota/release-${VERSION}/tasmota-lite.bin" &&
    wget -q -O "${ROOT_DIR}/src/build/resources/firmware/tasmota-minimal-${VERSION}.bin.gz" "http://ota.tasmota.com/tasmota/release-${VERSION}/tasmota-minimal.bin.gz" &&
    wget -q -O "${ROOT_DIR}/src/build/resources/firmware/tasmota32-${VERSION}.bin" "http://ota.tasmota.com/tasmota32/release/tasmota32.bin"; }; then
    rm -rf "${ROOT_DIR}/src/build/resources/firmware/"*.gz "${ROOT_DIR}/src/build/resources/firmware/"*.bin
    echo "Firmware download failed [${VERSION}]" >&2
    exit 1
  fi
fi

MQTT_VERSION=5.10.1
if [ ! -s "${ROOT_DIR}/src/main/resources/image/html/mqtt.min.js" ]; then
  if ! { mkdir -p "${ROOT_DIR}/src/main/resources/image/html" &&
    wget -q -O "${ROOT_DIR}/src/main/resources/image/html/mqtt.min.js" "https://unpkg.com/mqtt@${MQTT_VERSION}/dist/mqtt.min.js"; }; then
    rm -f "${ROOT_DIR}/src/main/resources/image/html/mqtt.min.js"
    echo "Download failed [mqtt.min.js]" >&2
    exit 1
  fi
fi

# NOTES: https://github.com/educlopez/thegridcn-ui (MIT), themes are data-theme attributes on <html>
if [ ! -s "${ROOT_DIR}/src/main/resources/image/html/ares.css" ]; then
  if ! { mkdir -p "${ROOT_DIR}/src/main/resources/image/html" &&
    wget -q -O "${ROOT_DIR}/src/main/resources/image/html/ares.css" "https://thegridcn.com/tokens/ares.css"; }; then
    rm -f "${ROOT_DIR}/src/main/resources/image/html/ares.css"
    echo "Download failed [ares.css]" >&2
    exit 1
  fi
fi
