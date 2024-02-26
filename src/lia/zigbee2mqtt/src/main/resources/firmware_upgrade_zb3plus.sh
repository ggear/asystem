docker run --rm \
  --device /dev/ttyUSBZB3DongleP:/dev/ttyUSBZB3DongleP \
  -e FIRMWARE_URL=https://github.com/Koenkk/Z-Stack-firmware/raw/Z-Stack_3.x.0_coordinator_20230507/coordinator/Z-Stack_3.x.0/bin/CC1352P2_CC2652P_launchpad_coordinator_20230507.zip \
  ckware/ti-cc-tool -ewv -p /dev/ttyUSBZB3DongleP --bootloader-sonoff-usb
