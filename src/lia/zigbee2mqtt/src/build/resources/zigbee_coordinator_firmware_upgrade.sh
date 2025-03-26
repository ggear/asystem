#!/bin/sh

# Product: Sonoff Zigbee 3.0 USB Dongle Plus (ZBDongle-P)
# Chipset: CC2652P
# Specifcations: https://sonoff.tech/wp-content/uploads/2021/11/产品参数表-ZBDongle-P-20211008.pdf
# Firmware:
#   - https://www.zigbee2mqtt.io/guide/adapters/zstack.html
#   - https://github.com/Koenkk/Z-Stack-firmware/tree/master/coordinator/Z-Stack_3.x.0/bin
#   - https://github.com/Koenkk/Z-Stack-firmware/raw/Z-Stack_3.x.0_coordinator_20230507/coordinator/Z-Stack_3.x.0/bin/CC1352P2_CC2652P_launchpad_coordinator_20230507.zip

docker run --rm \
  --device /dev/ttyUSBZB3DongleP:/dev/ttyUSBZB3DongleP \
  -e FIRMWARE_URL=https://github.com/Koenkk/Z-Stack-firmware/raw/Z-Stack_3.x.0_coordinator_20230507/coordinator/Z-Stack_3.x.0/bin/CC1352P2_CC2652P_launchpad_coordinator_20230507.zip \
  ckware/ti-cc-tool -ewv -p /dev/ttyUSBZB3DongleP --bootloader-sonoff-usb
