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
# Norm installs
################################################################################
# fab release ./macmini-nel_macmini-liz_macbook-flo/host
# fab release ./macmini-nel_macmini-liz_macbook-flo/keys
# fab release ./macmini-nel_macmini-liz_macbook-flo/monitor
# fab release ./udm-rack_macmini-liz_macmini-nel_macbook-flo/host
# fab release ./udm-rack_macmini-liz_macmini-nel_macbook-flo/users
