#!/bin/bash

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
