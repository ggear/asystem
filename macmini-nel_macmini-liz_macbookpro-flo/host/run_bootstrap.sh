#!/bin/bash

################################################################################
# Install system
################################################################################
# Debian 11 (bullyseye amd64 net iso)
# Install (non-graphical)
# Dont load proprietary media
# Set host to ${HOST_TYPE}-${HOST_NAME}.janeandgraham.com (macmini-liz, macmini-nel, macbookpro-flo)
# Create user graham
# Guided entire disk and setup LVM create partitions at 450GB, /tmp, /var, /home, max, force UEFI
# Install SSH server, standard sys utils


################################################################################
# Bootstrap system
################################################################################
# Enable remote root login : /etc/ssh/sshd_config PermitRootLogin yes
# Second HDD (1.9TB), single partition and added to fstab as per:
#fdisk -l
#blkid /dev/sdb
#fdisk /dev/sdb
#mkfs.ext4 -j /dev/sdb1
#blkid /dev/sdb1
#echo "/dev/sdb1 /data ext4 defaults 1 2" >>/etc/fstab
#mount -a
