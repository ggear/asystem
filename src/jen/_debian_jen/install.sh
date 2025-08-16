#!/bin/bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

################################################################################
# Volumes
################################################################################
${SERVICE_INSTALL}/volumes.sh || exit 1

################################################################################
# Storage
################################################################################
grep -q 'usb-storage.quirks=174c:235c:u' /boot/firmware/cmdline.txt || sed -i '1 s/$/ usb-storage.quirks=174c:235c:u/' /boot/firmware/cmdline.txt

################################################################################
# Wireless
################################################################################
[ ! -f /etc/modprobe.d/blacklist-brcmfmac.conf ] && echo "blacklist brcmfmac" | tee -a /etc/modprobe.d/blacklist-brcmfmac.conf

################################################################################
# Bluetooth
################################################################################
grep -qxF 'DISABLE_BT=1' /etc/default/raspi-firmware || echo 'DISABLE_BT=1' | tee -a /etc/default/raspi-firmware

################################################################################
# Image
################################################################################
update-initramfs -u -k all

################################################################################
# Unused services
################################################################################
systemctl stop smbd
systemctl disable smbd
systemctl mask smbd
systemctl stop nmbd
systemctl disable nmbd
systemctl mask nmbd
systemctl stop smartmontools
systemctl disable smartmontools
systemctl mask smartmontools
