#!/bin/bash

################################################################################
# Bootable USB
################################################################################
diskutil list /dev/disk4
umount /dev/disk4
wget http://debian.mirror.digitalpacific.com.au/debian-cd/11.5.0/amd64/iso-cd/debian-11.5.0-amd64-netinst.iso
dd if=/Users/graham/Desktop/debian-11.5.0-amd64-netinst.iso bs=1m | /opt/homebrew/bin/pv /Users/graham/Desktop/debian-11.5.0-amd64-netinst.iso | dd of=/dev/disk4 bs=1m
diskutil eject /dev/disk4

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
# Run install.sh apt-get install commands, ignore errors (eg docker/containerio)
# Run run_upgrade script

################################################################################
# Bootstrap system
################################################################################
sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
systemctl restart ssh

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