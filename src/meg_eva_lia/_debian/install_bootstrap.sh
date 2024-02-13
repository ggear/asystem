#!/bin/bash

################################################################################
# Bootable USB
################################################################################
diskutil list /dev/disk2
diskutil unmountDisk force /dev/disk2
wget http://debian.mirror.digitalpacific.com.au/debian-cd/12.4.0/amd64/iso-cd/debian-12.4.0-amd64-netinst.iso
dd if=/Users/graham/Desktop/debian-12.4.0-amd64-netinst.iso bs=1m | /usr/local/bin/pv /Users/graham/Desktop/debian-12.4.0-amd64-netinst.iso | dd of=/dev/disk2 bs=1m

################################################################################
# Install system
################################################################################
# Install (non-graphical)
# Dont load proprietary media
# Set host to ${HOST_TYPE}-${HOST_NAME}.janeandgraham.com
# Create user Graham Gear (graham)
# Guided entire disk and setup LVM create partitions at 450GB, /tmp, /var, /home, max, force UEFI
# Install SSH server, standard sys utils

################################################################################
# Install packages
################################################################################
# Run install_upgrade.sh script
# Run install.sh apt-get install commands

################################################################################
# SSH config
################################################################################
sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
systemctl restart ssh

################################################################################
# Network (USB)
################################################################################
apt-get install -y --allow-downgrades 'firmware-realtek=20210315-3'
INTERFACE=$(lshw -C network -short 2>/dev/null | grep enx | tr -s ' ' | cut -d' ' -f2)
if [ "${INTERFACE}" != "" ] && ifconfig "${INTERFACE}" >/dev/null && [ $(grep "${INTERFACE}" /etc/network/interfaces | wc -l) -eq 0 ]; then
  cat <<EOF >>/etc/network/interfaces

rename ${INTERFACE}=lan0
allow-hotplug lan0
iface lan0 inet dhcp
    pre-up ethtool -s lan0 speed 1000 duplex full autoneg off
EOF
fi
cat <<EOF >/etc/udev/rules.d/10-usb-network-realtek.rules
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="0bda", ATTR{idProduct}=="8153", TEST=="power/autosuspend", ATTR{power/autosuspend}="-1"
EOF
chmod -x /etc/udev/rules.d/10-usb-network-realtek.rules
echo "Power management disabled for: "$(find -L /sys/bus/usb/devices/*/power/autosuspend -exec echo -n {}": " \; -exec cat {} \; | grep ": \-1")
