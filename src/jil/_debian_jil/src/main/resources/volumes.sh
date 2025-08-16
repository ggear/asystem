#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

fstab_file="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/fstab"
if [ ! -f "$fstab_file" ]; then
  echo && echo "#######################################################################################"
  echo "Could not find fstab file [${fstab_file}]"
  echo "#######################################################################################" && echo
  exit 1
fi
cp -rvf "$fstab_file" /etc/fstab
command -v smbd >/dev/null && systemctl stop smbd
for _dir in $(mount | grep /share | awk '{print $3}'); do umount -f ${_dir}; done
[ -n "$(find /share -mindepth 2 -type f 2>/dev/null)" ] && {
  echo && echo "#######################################################################################"
  echo "Could not unmount all shares"
  echo "#######################################################################################" && echo
  exit 1
}
find /share -mindepth 1 -type d -empty -delete 2>/dev/null
for _dir in $(grep -v '^#' /etc/fstab | grep '/share\|/backup' | awk '{print $2}'); do mkdir -p ${_dir} && chmod 750 ${_dir} && chown graham:users ${_dir}; done
command -v smbd >/dev/null && systemctl start smbd
if mount -a 2>/tmp/mount_errors.log; then
  echo "All /etc/fstab entries mounted successfully"
else
  echo && echo "#######################################################################################"
  echo "Errors encountered mounting /etc/fstab entries:"
  echo "#######################################################################################" && echo
  cat /tmp/mount_errors.log
fi
systemctl daemon-reload
systemctl list-units --type=automount --no-legend | grep 'share-'
for share_automount_unit in $(systemctl list-units --type=automount --no-legend | grep 'share-' | awk '/share-[0-9]+\.automount$/ {print $2}'); do
  systemctl stop "$share_automount_unit"
  systemctl disable "$share_automount_unit"
done
systemctl daemon-reload
systemctl reset-failed
systemctl list-units --type=automount --no-legend
duf -width 250 -style ascii -output  mountpoint,size,used,avail,usage /share/*

echo "✅ Volumes configured"