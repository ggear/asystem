#!/bin/bash

################################################################################
# Hardware specs
################################################################################
# macmini-nel: Mid 2011 (5,2) https://everymac.com/systems/apple/mac_mini/specs/mac-mini-core-i5-2.5-mid-2011-specs.html
# macmini-liz: Late 2012 (6,1) https://everymac.com/systems/apple/mac_mini/specs/mac-mini-core-i5-2.5-late-2012-specs.html
# macbook-flo: Late 2013 (11,3) https://everymac.com/systems/apple/macbook_pro/specs/macbook-pro-core-i7-2.3-15-dual-graphics-late-2013-retina-display-specs.html

################################################################################
# Bootable USB
################################################################################
diskutil list /dev/disk2
umount /dev/disk2
wget https://laotzu.ftp.acc.umu.se/debian-cd/current/amd64/iso-cd/debian-11.1.0-amd64-netinst.iso
dd if=/Users/graham/Desktop/debian-11.1.0-amd64-netinst.iso bs=1m | pv /Users/graham/Desktop/debian-11.1.0-amd64-netinst.iso | dd of=/dev/disk2 bs=1m
diskutil eject /dev/disk2

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
# Run run.sh apt-get install commands, ignore errors (eg docker/containerio)
# Run run_upgrade script

################################################################################
# Bootstrap system
################################################################################
sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
systemctl restart ssh

################################################################################
# Network USB (if required)
################################################################################
ip a | grep 192
lshw -C network -short
ifconfig enx00e04c680421
cat <<EOF >>/etc/network/interfaces

allow-hotplug enx00e04c680421
iface enx00e04c680421 inet dhcp

EOF
ifup -a
ip a | grep 192

################################################################################
# Install HDD (if required)
################################################################################
fdisk -l
blkid /dev/sdb
fdisk /dev/sdx
mkfs.ext4 -j /dev/sdx1
blkid /dev/sdx1
blkid | grep " UUID=" | grep -v mapper | grep -v PARTLABEL | grep BLOCK_SIZE
echo "UUID=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX  /data           ext4    rw,user,exec,auto,async,nofail        0       2" >>/etc/fstab
mount -a

################################################################################
# Volumes
################################################################################
vgdisplay
lvdisplay /dev/$(hostname)-vg/var
lvextend -L30G /dev/$(hostname)-vg/var
resize2fs /dev/$(hostname)-vg/var
lvdisplay /dev/$(hostname)-vg/var
df -h /var

################################################################################
# Mount options
################################################################################
cat <<EOF >>/etc/fstab

# <file system>                            <mount point>   <type>  <options>                             <dump>  <pass>
#/dev/mapper/macmini--nel--vg-root          /               ext4    noatime,commit=600,errors=remount-ro  0       1
#UUID=51e5d8b5-1614-473e-85ce-eea631757e3b  /boot           ext2    noatime,defaults                      0       2
#UUID=6B88-1A36                             /boot/efi       vfat    umask=0077                            0       1
#/dev/mapper/macmini--nel--vg-home          /home           ext4    noatime,commit=600,errors=remount-ro  0       2
#/dev/mapper/macmini--nel--vg-tmp           /tmp            ext4    noatime,commit=600,errors=remount-ro  0       2
#/dev/mapper/macmini--nel--vg-var           /var            ext4    noatime,commit=600,errors=remount-ro  0       2
#/dev/mapper/macmini--nel--vg-swap_1        none            swap    sw                                    0       0
#UUID=89b36041-a92a-4364-8080-339e84280eb4  /data           ext4    rw,user,exec,auto,async,nofail        0       2
EOF

################################################################################
# Normalisation
################################################################################
cd /Users/graham/_/dev/asystem/macmini-nel_macmini-liz_macbook-flo/host-keys && fab release
cd /Users/graham/_/dev/asystem/udm-rack_macmini-liz_macmini-nel_macbook-flo/host-users && fab release
cd /Users/graham/_/dev/asystem/udm-rack_macmini-liz_macmini-nel_macbook-flo/host-home && fab release
cd /Users/graham/_/dev/asystem/macmini-nel_macmini-liz_macbook-flo/host-debian && fab release
