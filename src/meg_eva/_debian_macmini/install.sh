#!/bin/bash

################################################################################
# Intel network card
################################################################################
if [ -f /etc/default/grub ] && [ $(grep "intel_iommu=on iommu=pt" /etc/default/grub | wc -l) -eq 0 ]; then
  sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT="quiet/GRUB_CMDLINE_LINUX_DEFAULT="quiet intel_iommu=on iommu=pt/' /etc/default/grub
  update-grub
fi

################################################################################
# Volumes LVM standard (assumes drive > 500GB)
################################################################################
vgdisplay
vgdisplay | grep 'Free  PE / Size'
lvdisplay | grep 'LV Size'
lvdisplay /dev/$(hostname)-vg/root
lvextend -L 25G /dev/$(hostname)-vg/root
resize2fs /dev/$(hostname)-vg/root
tune2fs -m 5 /dev/$(hostname)-vg/root
tune2fs -l /dev/$(hostname)-vg/root | grep 'Block size:'
tune2fs -l /dev/$(hostname)-vg/root | grep 'Block count:'
tune2fs -l /dev/$(hostname)-vg/root | grep 'Reserved block count:'
lvdisplay /dev/$(hostname)-vg/root
df -h /root
vgdisplay
lvdisplay /dev/$(hostname)-vg/var
lvextend -L 30G /dev/$(hostname)-vg/var
resize2fs /dev/$(hostname)-vg/var
tune2fs -m 5 /dev/$(hostname)-vg/var
tune2fs -l /dev/$(hostname)-vg/var | grep 'Block size:'
tune2fs -l /dev/$(hostname)-vg/var | grep 'Block count:'
tune2fs -l /dev/$(hostname)-vg/var | grep 'Reserved block count:'
lvdisplay /dev/$(hostname)-vg/var
df -h /var
vgdisplay
lvdisplay /dev/$(hostname)-vg/tmp
lvextend -L 20G /dev/$(hostname)-vg/tmp
resize2fs /dev/$(hostname)-vg/tmp
tune2fs -m 5 /dev/$(hostname)-vg/tmp
tune2fs -l /dev/$(hostname)-vg/tmp | grep 'Block size:'
tune2fs -l /dev/$(hostname)-vg/tmp | grep 'Block count:'
tune2fs -l /dev/$(hostname)-vg/tmp | grep 'Reserved block count:'
lvdisplay /dev/$(hostname)-vg/tmp
df -h /tmp
vgdisplay
lvdisplay /dev/$(hostname)-vg/home
lvextend -L 412G /dev/$(hostname)-vg/home
resize2fs /dev/$(hostname)-vg/home
tune2fs -m 5 /dev/$(hostname)-vg/home
tune2fs -l /dev/$(hostname)-vg/home | grep 'Block size:'
tune2fs -l /dev/$(hostname)-vg/home | grep 'Block count:'
tune2fs -l /dev/$(hostname)-vg/home | grep 'Reserved block count:'
lvdisplay /dev/$(hostname)-vg/home
df -h /home

################################################################################
# Install SSD (entire disk to be allocated)
################################################################################
if fdisk -l /dev/sda >/dev/null 2>&1 && ! fdisk -l /dev/sda1 >/dev/null 2>&1; then
  fdisk -l
  blkid /dev/sda
  parted /dev/sda
  # mklabel gpt
  # mkpart primary 0% 100%
  # quit
  mkfs.ext4 -m 0 -T largefile4 /dev/sda1
  tune2fs -m 0 /dev/sda1
  blkid /dev/sda1
fi
fdisk -l /dev/sda1

################################################################################
# Network (Onboard)
################################################################################
echo "macvlan" | sudo tee -a /etc/modules
INTERFACE=$(lshw -C network -short -c network 2>/dev/null | tr -s ' ' | cut -d' ' -f2 | grep -v 'path\|=\|network')
if [ "${INTERFACE}" != "" ] && ifconfig "${INTERFACE}" >/dev/null && [ $(grep "auto eth0." /etc/network/interfaces | wc -l) -eq 0 ]; then
  MACADDRESS_SUFFIX="$(ifconfig "${INTERFACE}" | grep ether | tr -s ' ' | cut -d' ' -f3 | cut -d':' -f2-)"
  if [ "${INTERFACE}" != "" ]; then
    cat <<EOF >>/etc/network/interfaces

rename ${INTERFACE}=eth0

auto eth0
iface eth0 inet dhcp

auto eth0.3
iface eth0.3 inet dhcp
    vlan-raw-device eth0
    pre-up ip link set eth0.3 address 3a:${MACADDRESS_SUFFIX}

auto eth0.4
iface eth0.4 inet dhcp
    vlan-raw-device eth0
    pre-up ip link set eth0.4 address 4a:${MACADDRESS_SUFFIX}

EOF
  fi
fi
