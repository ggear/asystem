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
sed -i 's/PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config
sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
systemctl restart ssh
# Copy install_upgrade.sh to shell and run
# Copy install.sh apt-get install commands to shell and run
# reboot now

################################################################################
# Resize LVM share
################################################################################
#SHARE_GUID="share_05"
#SHARE_SIZE="3.1TB"
if [ -n "${SHARE_GUID}" ] && [ -n "${SHARE_SIZE}" ]; then
  vgdisplay
  if ! lvdisplay /dev/$(hostname)-vg/${SHARE_GUID} >/dev/null 2>&1; then
    lvcreate -L ${SHARE_SIZE} -n ${SHARE_GUID} $(hostname)-vg
    mkfs.ext4 -m 0 -T largefile4 /dev/$(hostname)-vg/${SHARE_GUID}
  fi
  lvdisplay /dev/$(hostname)-vg/${SHARE_GUID}
  lvextend -L ${SHARE_SIZE} /dev/$(hostname)-vg/${SHARE_GUID}
  resize2fs /dev/$(hostname)-vg/${SHARE_GUID}
  tune2fs -m 0 /dev/$(hostname)-vg/${SHARE_GUID}
  tune2fs -l /dev/$(hostname)-vg/${SHARE_GUID} | grep 'Block size:'
  tune2fs -l /dev/$(hostname)-vg/${SHARE_GUID} | grep 'Block count:'
  tune2fs -l /dev/$(hostname)-vg/${SHARE_GUID} | grep 'Reserved block count:'
  lvdisplay /dev/$(hostname)-vg/${SHARE_GUID}
fi
vgdisplay | grep 'Free  PE / Size'
lvdisplay | grep 'LV Size'

################################################################################
# Install SSD (entire disk to be allocated)
################################################################################
SHARE_GUID="share_10"
dev_recent=$(ls -lt --time-style=full-iso /dev/disk/by-id/ | grep usb | sort -k6,7 -r | head -n 1 | awk '{print $NF}')
if [ -n "${dev_recent}" ]; then
  dev_path="/dev/$(lsblk -no $(echo "${dev_recent}" | grep -q '[0-9]$' && echo 'pk')name "$(readlink -f /dev/disk/by-id/"${dev_recent}")" | head -n 1)"
  dev_name=$(basename "${dev_path}")
  echo "" && lsblk -o NAME,KNAME,TRAN,SIZE,MOUNTPOINT,MODEL,SERIAL,VENDOR && echo ""
  if [ -b "${dev_path}" ]; then
    echo "" && lsblk -o NAME,KNAME,TRAN,SIZE,MOUNTPOINT,MODEL,SERIAL,VENDOR "${dev_path}" && echo ""
    dmesg | grep "${dev_name}" | tail -n 10
    echo "" && echo ""
    echo "################################################################################"
    echo "Found USB block device: ${dev_path}"
    echo "################################################################################"
    echo ""
  else
    echo "Resolved device is not a block device: ${dev_path}"
  fi
else
  echo "No USB block devices found in /dev/disk/by-id/"
fi
if [ -n "${SHARE_GUID}" ]; then
  if [ -n "${dev_path}" ]; then
    echo "" && fdisk -l "${dev_path}" && echo "" && lsblk "${dev_path}" && echo ""
    if fdisk -l "${dev_path}" >/dev/null 2>&1 && ! fdisk -l "${dev_path}"1 >/dev/null 2>&1; then
      parted "${dev_path}"
      # mklabel gpt
      # mkpart primary 0% 100%
      # quit
      echo "" && fdisk -l "${dev_path}" && echo "" && lsblk "${dev_path}" && echo ""
      mkfs.ext4 -m 0 -T largefile4 "${dev_path}"1
      tune2fs -m 0 "${dev_path}"1
      parted "${dev_path}" name 1 ${SHARE_GUID}
      blkid "${dev_path}"1
      # Update /etc/fstab in _debain_$HOST service
    else
      echo "USB block device has existing file system: ${dev_path}"
    fi
  fi
fi

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
