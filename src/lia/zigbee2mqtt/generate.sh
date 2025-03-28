#!/bin/bash

. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

VERSION_DATE=20230507
VERSION=Z-Stack_3.x.0_coordinator_${VERSION_DATE}
# Product: Sonoff Zigbee 3.0 USB Dongle Plus (ZBDongle-P)
# Chipset: CC2652P
# Specifications: https://sonoff.tech/wp-content/uploads/2021/11/产品参数表-ZBDongle-P-20211008.pdf
# Firmware: https://github.com/Koenkk/Z-Stack-firmware/tree/master/coordinator/Z-Stack_3.x.0/bin
# Upgrade: docker run --rm --device /dev/ttyUSBZB3DongleP:/dev/ttyUSBZB3DongleP -e FIRMWARE_URL=https://github.com/Koenkk/Z-Stack-firmware/raw/${VERSION}/coordinator/Z-Stack_3.x.0/bin/CC1352P2_CC2652P_launchpad_coordinator_${VERSION_DATE}.zip kware/ti-cc-tool -ewv -p /dev/ttyUSBZB3DongleP --bootloader-sonoff-usb
pull_repo "${ROOT_DIR}" "${1}" zigbee2mqtt z-stack-firmware koenkk/z-stack-firmware "${VERSION}"

rm -rf "${ROOT_DIR}/src/main/resources/image/mqtt/"*.py
for PY_FILE in "${ROOT_DIR}/src/main/python/zigbee2mqtt/"*.py; do
  PY_PATH="${ROOT_DIR}/src/main/resources/image/mqtt/$(basename "${PY_FILE}")"
  echo -e "#!/usr/bin/env python\n\n\"\"\"\nWARNING: This file is written by the build process, any manual edits will be lost!\n\"\"\"\n" >"${PY_PATH}"
  cat "${PY_FILE}" >>"${PY_PATH}"
  chmod +x "${PY_PATH}"
done
