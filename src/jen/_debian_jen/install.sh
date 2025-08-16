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
grep -q 'usb-storage.quirks=174c:235c:u' /boot/cmdline.txt || sed -i '1 s/$/ usb-storage.quirks=174c:235c:u/' /boot/cmdline.txt

################################################################################
# Wireless
################################################################################
[ ! -f /etc/modprobe.d/blacklist-brcmfmac.conf ] && echo "blacklist brcmfmac" | tee -a /etc/modprobe.d/blacklist-brcmfmac.conf

################################################################################
# Bluetooth
################################################################################
grep -qxF 'dtoverlay=disable-bt' /boot/firmware/config.txt || echo 'dtoverlay=disable-bt' | tee -a /boot/firmware/config.txt && systemctl disable --now hciuart.service

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

################################################################################
# Regenerate initramfs
################################################################################
update-initramfs -u
