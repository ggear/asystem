#!/bin/bash

################################################################################
# Volumes LVM share
################################################################################
SHARE_GUID="2"
SHARE_SIZE="3.1TB"
if [ -n "${SHARE_GUID}" ] && [ -n "${SHARE_SIZE}" ]; then
  vgdisplay
  if ! lvdisplay /dev/$(hostname)-vg/share-${SHARE_GUID} >/dev/null 2>&1; then
    lvcreate -L ${SHARE_SIZE} -n share-${SHARE_GUID} $(hostname)-vg
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
blkid
fstab_file="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/fstab"
if [ -f "$fstab_file" ]; then
  cp -rvf "$fstab_file" /etc/fstab
  if mount -a 2>/tmp/mount_errors.log; then
    echo "All /etc/fstab entries mounted successfully"
  else
    echo "Errors encountered mounting /etc/fstab entries:"
    cat /tmp/mount_errors.log
    exit 1
  fi
  systemctl daemon-reload
  for _dir in $(grep -v '^#' /etc/fstab | grep '/share\|/backup' | awk '{print $2}'); do mkdir -p ${_dir} && chmod 750 ${_dir} && chown graham:users ${_dir}; done
fi
systemctl list-units --type=automount --no-legend | grep 'share-'
for share_automount_unit in $(systemctl list-units --type=automount --no-legend | grep 'share-' | awk '/share-[0-9]+\.automount$/ {print $2}'); do
  systemctl stop "$share_automount_unit"
  systemctl disable "$share_automount_unit"
done
systemctl daemon-reload
systemctl reset-failed
systemctl list-units --type=automount --no-legend
duf /share/*
