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
grep -qxF 'dtoverlay=disable-bt' /boot/firmware/config.txt || echo 'dtoverlay=disable-bt' | tee -a /boot/firmware/config.txt

################################################################################
# Image
################################################################################
update-initramfs -u -k all

################################################################################
# Unused services
################################################################################
for _service in smbd nmbd smartmontools hciuart bluetooth wpa_supplicant; do
  if systemctl list-unit-files "$_service.service" >/dev/null 2>&1; then
    echo -n "Stopping $_service ... " && (systemctl stop "$_service" 2>/dev/null || true) && echo "done"
    echo -n "Disabling $_service ... " && (systemctl disable "$_service" 2>/dev/null || true) && echo "done"
    echo -n "Masking $_service ... " && (systemctl mask "$_service" 2>/dev/null || true) && echo "done"
  else
    echo "Service $_service not found, skipping."
  fi
done
