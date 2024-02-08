#!/bin/bash

################################################################################
# Bootable USB
################################################################################
diskutil list /dev/disk2
diskutil unmountDisk force /dev/disk2
wget http://debian.mirror.digitalpacific.com.au/debian-cd/12.0.0/amd64/iso-cd/debian-12.0.0-amd64-netinst.iso
dd if=/Users/graham/Desktop/debian-12.0.0-amd64-netinst.iso bs=1m | /usr/local/bin/pv /Users/graham/Desktop/debian-12.0.0-amd64-netinst.iso | dd of=/dev/disk2 bs=1m

################################################################################
# Install system
################################################################################
# Install (non-graphical)
# Dont load proprietary media
# Set host to ${HOST_TYPE}-${HOST_NAME}.janeandgraham.com (macmini-liz, macmini-nel, macbook-flo)
# Create user Graham Gear (graham)
# Guided entire disk and setup LVM create partitions at 450GB, /tmp, /var, /home, max, force UEFI
# Install SSH server, standard sys utils

################################################################################
# Install packages
################################################################################
# Run install_upgrade.sh script
# Run install.sh apt-get install commands

################################################################################
# Bootstrap system
################################################################################
sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
systemctl restart ssh

################################################################################
# Install HDD (if required)
################################################################################
fdisk -l
blkid /dev/sdx
fdisk /dev/sdx
mkfs.ext4 -j /dev/sdx1
tune2fs -m 0 /dev/sdx1
blkid /dev/sdx1
blkid | grep " UUID=" | grep -v mapper | grep -v PARTLABEL | grep BLOCK_SIZE
echo "UUID=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX  /data           ext4    rw,user,exec,auto,async,nofail        0       2" >>/etc/fstab
mount -a

################################################################################
# Volumes /var
################################################################################
vgdisplay
lvdisplay /dev/$(hostname)-vg/var
lvextend -L30G /dev/$(hostname)-vg/var
resize2fs /dev/$(hostname)-vg/var
lvdisplay /dev/$(hostname)-vg/var
df -h /var

################################################################################
# Volumes /data (if required)
################################################################################
vgdisplay
# /data/tmp
lvcreate -L 200G -n data-tmp macmini-meg-vg
mkfs.ext4 -j /dev/macmini-meg-vg/data-tmp
tune2fs -m 0 /dev/macmini-meg-vg/data-tmp
lvdisplay /dev/macmini-meg-vg/data-tmp
# /data/backup
lvcreate -L 100G -n data-backup macmini-meg-vg
mkfs.ext4 -j /dev/macmini-meg-vg/data-backup
tune2fs -m 0 /dev/macmini-meg-vg/data-backup
lvdisplay /dev/macmini-meg-vg/data-backup
# /data/media/audio
lvcreate -L 110G -n data-media-audio macmini-meg-vg
mkfs.ext4 -j /dev/macmini-meg-vg/data-media-audio
tune2fs -m 0 /dev/macmini-meg-vg/data-media-audio
lvdisplay /dev/macmini-meg-vg/data-media-audio
# /data/media/movies
lvcreate -L 750G -n data-media-movies macmini-meg-vg
mkfs.ext4 -j /dev/macmini-meg-vg/data-media-movies
tune2fs -m 0 /dev/macmini-meg-vg/data-media-movies
lvdisplay /dev/macmini-meg-vg/data-media-movies

################################################################################
# Mount points (if required)
################################################################################
mkdir -p /data/tmp
mkdir -p /data/backup
mkdir -p /data/media/audio
mkdir -p /data/media/movies
mkdir -p /data/media/series

################################################################################
# Mount options
################################################################################
cat <<EOF >>/etc/fstab
# <file system>                                  <mount point>             <type>  <options>                             <dump>  <pass>
/dev/mapper/macmini--meg--vg-root                /                         ext4    noatime,commit=600,errors=remount-ro  0       1
UUID=e296cb8a-0a02-413e-8e53-8bada21a610c        /boot                     ext2    noatime,defaults                      0       2
UUID=9B6D-5F3E                                   /boot/efi                 vfat    umask=0077                            0       1
/dev/mapper/macmini--meg--vg-home                /home                     ext4    noatime,commit=600,errors=remount-ro  0       2
/dev/mapper/macmini--meg--vg-tmp                 /tmp                      ext4    noatime,commit=600,errors=remount-ro  0       2
/dev/mapper/macmini--meg--vg-var                 /var                      ext4    noatime,commit=600,errors=remount-ro  0       2
/dev/mapper/macmini--meg--vg-swap_1              none                      swap    sw                                    0       0
/dev/mapper/macmini--meg--vg-data--tmp           /data/tmp                 ext4    noatime,commit=600,errors=remount-ro  0       2
/dev/mapper/macmini--meg--vg-data--backup        /data/backup              ext4    noatime,commit=600,errors=remount-ro  0       2
/dev/mapper/macmini--meg--vg-data--media--audio  /data/media/1             ext4    noatime,commit=600,errors=remount-ro  0       2
/dev/mapper/macmini--meg--vg-data--media--movies /data/media/2             ext4    noatime,commit=600,errors=remount-ro  0       2
UUID=100f5ef4-e75d-41f4-bcb9-aaa84c03209a        /data/media/3             ext4    noatime,commit=600,errors=remount-ro  0       2
EOF
df -h -t ext4
#Filesystem                                        Size  Used Avail Use% Mounted on
#/dev/mapper/macmini--meg--vg-home                 377G   19G  339G   6% /home
#/dev/mapper/macmini--meg--vg-tmp                  1.8G   64K  1.7G   1% /tmp
#/dev/mapper/macmini--meg--vg-var                   30G  8.6G   20G  31% /var
#/dev/mapper/macmini--meg--vg-root                  23G  7.8G   14G  36% /
#/dev/mapper/macmini--meg--vg-data--tmp            196G  151M  196G   1% /data/tmp
#/dev/mapper/macmini--meg--vg-data--backup          98G  2.1G   96G   3% /data/backup
#/dev/mapper/macmini--meg--vg-data--media--audio   108G  105G  3.6G  97% /data/media/1
#/dev/mapper/macmini--meg--vg-data--media--movies  738G  738G   21M 100% /data/media/2
#/dev/sda1                                         3.6T  3.6T  5.9G 100% /data/media/3

################################################################################
# Network (Onboard)
################################################################################
INTERFACE=$(lshw -C network -short 2>/dev/null | grep enp | tr -s ' ' | cut -d' ' -f2)
if [ "${INTERFACE}" != "" ] && ifconfig "${INTERFACE}" >/dev/null && [ $(grep "${INTERFACE}" /etc/network/interfaces | wc -l) -eq 0 ]; then
  cat <<EOF >>/etc/network/interfaces

rename ${INTERFACE}=lan0
allow-hotplug lan0
iface lan0 inet dhcp
    pre-up ethtool -s lan0 speed 1000 duplex full autoneg off
EOF
fi

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
