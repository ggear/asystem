#!/bin/bash

################################################################################
# Packages
################################################################################
apt-get update
apt-get install -y --allow-downgrades 'mbpfan=2.3.0-1+b1'
apt-get install -y --allow-downgrades 'libc6-i386=2.36-9+deb12u10'
apt-get install -y --allow-downgrades 'intel-microcode=3.20250512.1~deb12u1'

################################################################################
# Network
################################################################################
if [ -f /etc/default/grub ] && [ $(grep "intel_iommu=on iommu=pt" /etc/default/grub | wc -l) -eq 0 ]; then
  sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT="quiet/GRUB_CMDLINE_LINUX_DEFAULT="quiet intel_iommu=on iommu=pt/' /etc/default/grub
  update-grub
fi
INTERFACE=$(lshw -C network -short -c network 2>/dev/null | tr -s ' ' | cut -d' ' -f2 | grep -v 'path\|=\|network')
if [ "${INTERFACE}" != "" ] && ifconfig "${INTERFACE}" >/dev/null && [ $(grep "auto eth0." /etc/network/interfaces | wc -l) -eq 0 ]; then
  MACADDRESS_SUFFIX="$(ifconfig "${INTERFACE}" | grep ether | tr -s ' ' | cut -d' ' -f3 | cut -d':' -f2-)"
  if [ "${INTERFACE}" != "" ]; then
    cat <<'EOF' >>/etc/network/interfaces

rename ${INTERFACE}=eth0

auto eth0
iface eth0 inet dhcp

#auto eth0.3
#iface eth0.3 inet dhcp
#    vlan-raw-device eth0
#    pre-up ip link set eth0.3 address 3a:${MACADDRESS_SUFFIX}
#
#auto eth0.4
#iface eth0.4 inet dhcp
#    vlan-raw-device eth0
#    pre-up ip link set eth0.4 address 4a:${MACADDRESS_SUFFIX}

EOF
  fi
fi
systemctl stop wpa_supplicant.service
systemctl disable wpa_supplicant.service
grep -q '^8021q' /etc/modules 2>/dev/null || echo '8021q' | tee -a /etc/modules
grep -q '^macvlan' /etc/modules 2>/dev/null || echo 'macvlan' | tee -a /etc/modules
grep -q '^blacklist applesmc' /etc/modprobe.d/blacklist-wifi.conf 2>/dev/null || echo 'blacklist applesmc' | tee -a /etc/modprobe.d/blacklist-applesmc.conf
grep -q '^blacklist bcma-pci-bridge' /etc/modprobe.d/blacklist-wifi.conf 2>/dev/null || echo 'blacklist bcma-pci-bridge' | tee -a /etc/modprobe.d/blacklist-wifi.conf

################################################################################
# Bluetooth
################################################################################
systemctl stop bluetooth.service
systemctl disable bluetooth.service
systemctl mask bluetooth.service
grep -q '^blacklist bluetooth' /etc/modprobe.d/blacklist-bluetooth.conf 2>/dev/null || echo 'blacklist bluetooth' | tee -a /etc/modprobe.d/blacklist-bluetooth.conf

################################################################################
# Thunderbolt
################################################################################
mkdir -p /etc/boltd
cat <<'EOF' >/etc/boltd/bolt.conf
[Authorization]
auto=yes
EOF
systemctl restart bolt
systemctl status bolt
boltctl

################################################################################
# Regenerate initramfs
################################################################################
update-initramfs -u

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
# Fan
################################################################################
cat <<'EOF' >/etc/mbpfan.conf
[general]
min_fan_speed = 1800
max_fan_speed = 6500
low_temp = 40
high_temp = 60
max_temp = 65
polling_interval = 1
EOF
curl -sf https://raw.githubusercontent.com/linux-on-mac/mbpfan/49f544fd8d596fa13d5525a5b042eee311568c67/mbpfan.service -o /etc/systemd/system/mbpfan.service
systemctl enable mbpfan.service
