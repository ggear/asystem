#!/bin/bash

################################################################################
# Bootable USB
################################################################################
# diskutil list /dev/disk2
# umount /dev/disk2
# wget https://laotzu.ftp.acc.umu.se/debian-cd/current/amd64/iso-cd/debian-11.1.0-amd64-netinst.iso
# dd if=/Users/graham/Desktop/debian-11.1.0-amd64-netinst.iso bs=1m | pv /Users/graham/Desktop/debian-11.1.0-amd64-netinst.iso | dd of=/dev/disk2 bs=1m
# diskutil eject /dev/disk2

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
# Bootstrap system
################################################################################
# Enable remote root login : /etc/ssh/sshd_config PermitRootLogin yes

################################################################################
# Install packages
################################################################################
# Run run_packages.sh
# Run run_upgrade.sh
# Run run_packages.sh
# Run run_update.sh

################################################################################
# Storage format
################################################################################
# Second HDD (1.9TB), single partition and added to fstab as per:
#fdisk -l
#blkid /dev/sdb
#fdisk /dev/sdb
#mkfs.ext4 -j /dev/sdb1
#blkid /dev/sdb1
#blkid | grep " UUID=" | grep -v mapper | grep -v PARTLABEL | grep BLOCK_SIZE
#echo "UUID=89b36041-a92a-4364-8080-339e84280eb4  /data           ext4    rw,user,exec,auto,async,nofail        0       2" >>/etc/fstab
#mount -a

################################################################################
# Mount options
################################################################################
# <file system>                            <mount point>   <type>  <options>                             <dump>  <pass>
#/dev/mapper/macmini--nel--vg-root          /               ext4    noatime,commit=600,errors=remount-ro  0       1
#UUID=51e5d8b5-1614-473e-85ce-eea631757e3b  /boot           ext2    noatime,commit=600,defaults           0       2
#UUID=6B88-1A36                             /boot/efi       vfat    umask=0077                            0       1
#/dev/mapper/macmini--nel--vg-home          /home           ext4    noatime,commit=600,errors=remount-ro  0       2
#/dev/mapper/macmini--nel--vg-tmp           /tmp            ext4    noatime,commit=600,errors=remount-ro  0       2
#/dev/mapper/macmini--nel--vg-var           /var            ext4    noatime,commit=600,errors=remount-ro  0       2
#/dev/mapper/macmini--nel--vg-swap_1        none            swap    sw                                    0       0
#UUID=89b36041-a92a-4364-8080-339e84280eb4  /data           ext4    rw,user,exec,auto,async,nofail        0       2
#/dev/mapper/macmini--nel--vg-docker        /var/lib/docker ext4    noatime,barrier=0,nofail              0       2


################################################################################
# Volumes
################################################################################
vgdisplay
lvdisplay
lvextend -L15G /dev/$(hostname)-vg/var
resize2fs /dev/$(hostname)-vg/var
lvdisplay /dev/$(hostname)-vg/var
df -h /var
systemctl stop docker.service
systemctl stop docker.socket
rm -rf /var/lib/docker
mkdir -p /var/lib/docker
lvcreate -L20G -n docker $(hostname)-vg
mkfs.ext4 -j /dev/$(hostname)-vg/docker
tune2fs -O ^has_journal /dev/$(hostname)-vg/docker
echo "/dev/mapper/"${HOSTNAME/-/--}"--vg-docker        /var/lib/docker ext4    noatime,barrier=0,commit=6000,nofail  0       2" >>/etc/fstab
mount -a
rm -rf /var/lib/docker/lost+found
systemctl start docker.service
systemctl start docker.socket
lvdisplay /dev/$(hostname)-vg/docker
df -h /var/lib/docker
vgdisplay

################################################################################
# Norm installs
################################################################################
# fab release ./macmini-nel_macmini-liz_macbook-flo/host
# fab release ./macmini-nel_macmini-liz_macbook-flo/keys
# fab release ./macmini-nel_macmini-liz_macbook-flo/monitor
# fab release ./udm-rack_macmini-liz_macmini-nel_macbook-flo/host
# fab release ./udm-rack_macmini-liz_macmini-nel_macbook-flo/users
