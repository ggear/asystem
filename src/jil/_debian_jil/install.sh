#!/bin/bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

################################################################################
# Mounts
################################################################################
blkid
cp -rvf ${SERVICE_INSTALL}/fstab /etc/fstab
mkdir -p /backup/1 /backup/2

################################################################################
# Wireless
################################################################################
[ ! -f /etc/modprobe.d/blacklist-brcmfmac.conf ] && echo "blacklist brcmfmac" | tee -a /etc/modprobe.d/blacklist-brcmfmac.conf

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
