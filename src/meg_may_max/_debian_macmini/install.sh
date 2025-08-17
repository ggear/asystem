#!/bin/bash

################################################################################
# Packages
################################################################################
apt-get update
apt-get install -y --allow-downgrades 'mbpfan=2.3.0-1+b1'
apt-get install -y --allow-downgrades 'libc6-i386=2.36-9+deb12u10'
apt-get install -y --allow-downgrades 'intel-microcode=3.20250512.1~deb12u1'

################################################################################
# Grub config
################################################################################
[ ! -f /etc/default/grub.bak ] && cp -v /etc/default/grub /etc/default/grub.bak
grep -q '^GRUB_TIMEOUT=' /etc/default/grub || echo 'GRUB_TIMEOUT=10' >>/etc/default/grub
sed -i '/^GRUB_TIMEOUT=/c\GRUB_TIMEOUT=10' /etc/default/grub || echo 'GRUB_TIMEOUT=10' >>/etc/default/grub
grep -q '^GRUB_CMDLINE_LINUX=' /etc/default/grub || echo 'GRUB_CMDLINE_LINUX=""' >>/etc/default/grub
sed -i -E '/^GRUB_CMDLINE_LINUX=/{
  /cgroup_enable=memory/! s/"$/ cgroup_enable=memory"/
  /swapaccount=1/! s/"$/ swapaccount=1"/
}' /etc/default/grub
grep -q '^GRUB_CMDLINE_LINUX_DEFAULT=' /etc/default/grub || echo 'GRUB_CMDLINE_LINUX_DEFAULT=""' >>/etc/default/grub
sed -i -E '/^GRUB_CMDLINE_LINUX_DEFAULT=/{
  /acpi_osi=!/! s/"$/ acpi_osi=!"/
  /acpi_osi=\\"Windows 2015\\"/! s/"$/ acpi_osi=\\"Windows 2015\\""/
  /acpi_backlight=vendor/! s/"$/ acpi_backlight=vendor"/
  /pcie_aspm=force/! s/"$/ pcie_aspm=force"/
  /intel_iommu=on/! s/"$/ intel_iommu=on"/
  /iommu=pt/! s/"$/ iommu=pt"/
}' /etc/default/grub
sed -i -E 's/^(GRUB_CMDLINE_LINUX(_DEFAULT)?)="\s+/\1="/' /etc/default/grub
diff -u /etc/default/grub.bak /etc/default/grub
grub-mkconfig -o /dev/null
update-grub

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
# Image
################################################################################
update-initramfs -u -k all

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
# Devices
################################################################################
cat <<'EOF' >/etc/udev/rules.d/98-usb-edgetpu.rules
SUBSYSTEMS=="usb", ATTRS{idVendor}=="1a6e", ATTRS{idProduct}=="089a", MODE="0664", TAG+="uaccess"
SUBSYSTEMS=="usb", ATTRS{idVendor}=="18d1", ATTRS{idProduct}=="9302", MODE="0664", TAG+="uaccess"
EOF
chmod -x /etc/udev/rules.d/98-usb-edgetpu.rules
lsusb
for DEV in $(find /dev -name ttyUSB?); do
  udevadm info ${DEV} | grep "P: "
  udevadm info -a -n ${DEV} | grep {idVendor} | head -1
  udevadm info -a -n ${DEV} | grep {idProduct} | head -1
  udevadm info -a -n ${DEV} | grep {serial} | head -1
  udevadm info -a -n ${DEV} | grep {product} | head -1
done
cat <<'EOF' >/etc/udev/rules.d/99-usb-serial.rules
SUBSYSTEM=="tty", ATTRS{idVendor}=="067b", ATTRS{idProduct}=="2303", ATTRS{product}=="USB-Serial Controller", SYMLINK+="ttyUSBTempProbe"
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", ATTRS{product}=="CP2102 USB to UART Bridge Controller", SYMLINK+="ttyUSBVantagePro2"
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", ATTRS{product}=="Sonoff Zigbee 3.0 USB Dongle Plus", SYMLINK+="ttyUSBZB3DongleP"
EOF
chmod -x /etc/udev/rules.d/99-usb-serial.rules
udevadm control --reload-rules && udevadm trigger && sleep 2
ls -la /dev/ttyUSB* 2>/dev/null || true

################################################################################
# Digitemp
################################################################################
if [ -L /dev/ttyUSBTempProbe ]; then
  mkdir -p /etc/digitemp
  digitemp_DS9097 -i -s /dev/ttyUSBTempProbe -c /etc/digitemp/temp_probe.conf
  digitemp_DS9097 -a -c /etc/digitemp/temp_probe.conf
else
  rm -rf /etc/digitemp*
fi

################################################################################
# Avahi
################################################################################
cat <<'EOF' >/etc/avahi/avahi-daemon.conf
[server]
use-ipv6=no
allow-interfaces=lan0
[publish]
publish-hinfo=no
publish-workstation=no
[reflector]
enable-reflector=no
EOF
#systemctl disable avahi-daemon.socket
#systemctl disable avahi-daemon.service
#systemctl stop avahi-daemon.service
systemctl enable avahi-daemon.socket
systemctl enable avahi-daemon.service
systemctl restart avahi-daemon.service
systemctl status avahi-daemon.service
avahi-browse -a -t
#avahi-browse _home-assistant._tcp -t -r
#avahi-publish -v -s "Home" _home-assistant._tcp 32401 "Testing"
#dns-sd -L Home _home-assistant._tcp local

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
