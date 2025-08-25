#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

fstab_file="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/fstab"
if [ ! -f "$fstab_file" ]; then
  echo && echo "❌ Could not find fstab file [${fstab_file}]" && echo
  exit 1
fi
[ ! -f /etc/fstab.bak ] && cp -v /etc/fstab /etc/fstab.bak
cp -rvf "$fstab_file" /etc/fstab
diff -uw /etc/fstab.bak /etc/fstab
! systemctl list-unit-files smbd.service | grep -q masked && systemctl is-active --quiet smbd && systemctl stop smbd
for _dir in /share /backup; do mkdir -p ${_dir} && chmod 750 ${_dir} && chown graham:users ${_dir}; done
for _dir in $(mount | grep '/share\|/backup' | awk '{print $3}'); do umount -f ${_dir}; done
[ "$(find /share /backup -mindepth 2 -maxdepth 2 | wc -l)" -gt 0 ] && {
  echo && echo "❌ Could not unmount all shares" && echo
  exit 1
}
find /share -mindepth 1 -maxdepth 1 -type d -empty -delete
find /backup -mindepth 1 -maxdepth 1 -type d -empty -delete
for _dir in $(grep -v '^#' /etc/fstab | grep '/share\|/backup' | awk '{print $2}'); do mkdir -p ${_dir} && chmod 750 ${_dir} && chown graham:users ${_dir}; done
! systemctl list-unit-files smbd.service | grep -q masked && ! systemctl is-active --quiet smbd && systemctl start smbd
if mount -a 2>/tmp/mount_errors.log; then
  echo "All /etc/fstab entries mounted successfully"
else
  echo "Errors encountered mounting /etc/fstab entries:"
  cat /tmp/mount_errors.log
fi
[ "$(find /share -mindepth 1 -maxdepth 1)" ] && duf -width 250 -style ascii -output mountpoint,size,used,avail,usage,filesystem /share/*
mount -a -O noauto
[ "$(find /backup -mindepth 2 -maxdepth 2)" ] && duf -width 250 -style ascii -output mountpoint,size,used,avail,usage,filesystem /backup/*
awk '$4 ~ /noauto/ {print $2}' /etc/fstab | while read mp; do mountpoint -q "$mp" && umount -f "$mp"; done
systemctl daemon-reload
for share_automount_unit in $(systemctl list-units --type=automount --no-legend | grep 'share-' | awk '/share-[0-9]+\.automount$/ {print $2}'); do
  systemctl stop "$share_automount_unit"
  systemctl disable "$share_automount_unit"
done
systemctl daemon-reload
systemctl reset-failed
echo && echo "✅ Volumes configured" && echo