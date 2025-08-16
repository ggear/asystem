#!/bin/bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

################################################################################
# Volumes
################################################################################
${SERVICE_INSTALL}/volumes.sh || exit 1

#################################################################################
# Firmware/Kernel config
#################################################################################
touch /boot/firmware/config.txt && [ ! -f /boot/firmware/config.txt.bak ] && cp -v /boot/firmware/config.txt /boot/firmware/config.txt.bak
grep -qxF 'DISABLE_BT=1' /boot/firmware/config.txt || echo 'DISABLE_BT=1' | tee -a /boot/firmware/config.txt
grep -qxF 'DISABLE_WIFI=1' /boot/firmware/config.txt || echo 'DISABLE_WIFI=1' | tee -a /boot/firmware/config.txt
grep -qxF 'dtoverlay=disable-bt' /boot/firmware/config.txt || echo 'dtoverlay=disable-bt' | tee -a /boot/firmware/config.txt
grep -qxF 'dtoverlay=disable-wifi' /boot/firmware/config.txt || echo 'dtoverlay=disable-wifi' | tee -a /boot/firmware/config.txt
diff -u /boot/firmware/config.txt /boot/firmware/config.txt.bak
if [ ! -f /etc/modprobe.d/blacklist-brcmfmac.conf ]; then
  echo "blacklist brcmfmac" | tee -a /etc/modprobe.d/blacklist-brcmfmac.conf
  echo "blacklist bcm2835-wifi" | tee -a /etc/modprobe.d/blacklist-brcmfmac.conf
fi

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
