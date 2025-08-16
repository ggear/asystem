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
touch /etc/default/raspi-firmware-custom && [ ! -f /etc/default/raspi-firmware-custom.bak ] && cp -v /etc/default/raspi-firmware-custom /etc/default/raspi-firmware-custom.bak
grep -qxF 'DISABLE_BT=1' /etc/default/raspi-firmware-custom || echo 'DISABLE_BT=1' | tee -a /etc/default/raspi-firmware-custom
grep -qxF 'DISABLE_WIFI=1' /etc/default/raspi-firmware-custom || echo 'DISABLE_WIFI=1' | tee -a /etc/default/raspi-firmware-custom
grep -qxF 'dtoverlay=disable-bt' /etc/default/raspi-firmware-custom || echo 'dtoverlay=disable-bt' | tee -a /etc/default/raspi-firmware-custom
grep -qxF 'dtoverlay=disable-wifi' /etc/default/raspi-firmware-custom || echo 'dtoverlay=disable-wifi' | tee -a /etc/default/raspi-firmware-custom
echo "/etc/default/raspi-firmware-custom:" && cat /etc/default/raspi-firmware-custom
update-initramfs -u -k all
diff -u /boot/firmware/config.txt /boot/firmware/config.txt.bak

################################################################################
# Unused services
################################################################################
for _service in smbd nmbd smartmontools bluetooth wpa_supplicant; do
  if systemctl list-unit-files "$_service.service" >/dev/null 2>&1; then
    echo -n "Stopping $_service ... " && (systemctl stop "$_service" 2>/dev/null || true) && echo "done"
    echo -n "Disabling $_service ... " && (systemctl disable "$_service" 2>/dev/null || true) && echo "done"
    echo -n "Masking $_service ... " && (systemctl mask "$_service" 2>/dev/null || true) && echo "done"
  else
    echo "Service $_service not found, skipping."
  fi
done
