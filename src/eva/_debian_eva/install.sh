#!/bin/bash

################################################################################
# Volumes LVM share
################################################################################
SHARE_GUID="3"
SHARE_SIZE="3TB"
if [ -n "${SHARE_GUID}" ] && [ -n "${SHARE_SIZE}" ]; then
  vgdisplay
  if ! lvdisplay /dev/$(hostname)-vg/share-${SHARE_GUID} >/dev/null 2>&1; then
    lvcreate -L 5G -n share-${SHARE_GUID} $(hostname)-vg
    mkfs.ext4 -m 0 -T largefile4 /dev/$(hostname)-vg/share-${SHARE_GUID}
  fi
  lvdisplay /dev/$(hostname)-vg/share-${SHARE_GUID}
  lvextend -L ${SHARE_SIZE} /dev/$(hostname)-vg/share-${SHARE_GUID}
  resize2fs /dev/$(hostname)-vg/share-${SHARE_GUID}
  tune2fs -m 0 /dev/$(hostname)-vg/share-${SHARE_GUID}
  tune2fs -l /dev/$(hostname)-vg/share-${SHARE_GUID} | grep 'Block size:'
  tune2fs -l /dev/$(hostname)-vg/share-${SHARE_GUID} | grep 'Block count:'
  tune2fs -l /dev/$(hostname)-vg/share-${SHARE_GUID} | grep 'Reserved block count:'
  lvdisplay /dev/$(hostname)-vg/share-${SHARE_GUID}
fi
vgdisplay | grep 'Free  PE / Size'
lvdisplay | grep 'LV Size'

################################################################################
# Mounts
################################################################################
blkid /dev/sda1
cat <<EOF >/etc/fstab
# /etc/fstab: static file system information.
#
# Use 'blkid' to print the universally unique identifier for a
# device; this may be used with UUID= as a more robust way to name devices
# that works even if disks are added and removed. See fstab(5).
#
# systemd generates mount units based on this file, see systemd.mount(5).
# Please run 'systemctl daemon-reload' after making changes here.
#
# <file system>                               <mount point>       <type>  <options>                                                                                                  <dump>  <pass>
UUID=5240-B518                                /boot/efi           vfat    umask=0077                                                                                                 0       1
UUID=0e18317e-205c-437c-a02f-dbb5efca26aa     /boot               ext2    noatime,defaults                                                                                           0       2
/dev/mapper/macmini--eva--vg-swap_1           none                swap    sw                                                                                                         0       0
/dev/mapper/macmini--eva--vg-root             /                   ext4    noatime,commit=600,errors=remount-ro                                                                       0       1
/dev/mapper/macmini--eva--vg-home             /home               ext4    noatime,commit=600,errors=remount-ro                                                                       0       2
/dev/mapper/macmini--eva--vg-tmp              /tmp                ext4    noatime,commit=600,errors=remount-ro                                                                       0       2
/dev/mapper/macmini--eva--vg-var              /var                ext4    noatime,commit=600,errors=remount-ro                                                                       0       2
/dev/mapper/macmini--eva--vg-share--3         /share/3            ext4    noatime,commit=600,errors=remount-ro                                                                       0       2
UUID=4ae1477d-6e38-4b5f-8492-79f5072dcc8d     /share/4            ext4    noatime,commit=600,errors=remount-ro                                                                       0       2
//macmini-meg/share-1                         /share/1            cifs    user=share1,password=${SHARE_1_PASSWORD},user,nofail,x-systemd.automount                                                      0       0
//macmini-meg/share-2                         /share/2            cifs    user=share4,password=${SHARE_2_PASSWORD},user,nofail,x-systemd.automount                                                      0       0
EOF
for SHARE_DIR in $(grep /share /etc/fstab | awk 'BEGIN{FS=OFS=" "}{print $2}'); do mkdir -p ${SHARE_DIR}; done
systemctl daemon-reload
mount -a
