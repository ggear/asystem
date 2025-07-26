#!/bin/bash

################################################################################
# Bootable USB
################################################################################
USB_DEV="/dev/disk4"
DEBIAN_VERSION="12.11.0"
cd "/Users/graham/Desktop"
wget "https://debian.mirror.digitalpacific.com.au/debian-cd/${DEBIAN_VERSION}/amd64/iso-cd/debian-${DEBIAN_VERSION}-amd64-netinst.iso"
diskutil list "${USB_DEV}"
[[ $(diskutil list "${USB_DEV}" | grep 'external' | wc -l) -eq 1 ]] && diskutil unmountDisk force "${USB_DEV}"
[[ $(diskutil list "${USB_DEV}" | grep 'external' | wc -l) -eq 1 ]] && sudo dd "if=/Users/graham/Desktop/debian-${DEBIAN_VERSION}-amd64-netinst.iso" bs=1m | pv "/Users/graham/Desktop/debian-${DEBIAN_VERSION}-amd64-netinst.iso" | sudo dd "of=${USB_DEV}" bs=1m

################################################################################
# Install system
################################################################################
# Install (non-graphical)
# Set host to ${HOST_TYPE}-${HOST_NAME}
# Set domain name to lan.janeandgraham.com
# Create user Graham Gear (graham)
# Guided entire disk and setup LVM create partitions at 450GB, /tmp, /var, /home, max, force UEFI
# Install SSH server, standard sys utils

################################################################################
# Boostrap environment via ssh graham@${HOST_TYPE}-${HOST_NAME}
################################################################################
su -
sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
systemctl restart ssh
# Copy install_upgrade.sh to shell and run
# Copy install.sh apt-get install commands to shell and run
# reboot now

################################################################################
# Legacy USB NIC steup (No longer used) via ssh graham@${HOST_TYPE}-${HOST_NAME}
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
