#!/bin/bash

LABEL="MEDIA2"
DRIVE="/dev/sdc"
PARTITION="${DRIVE}1"
MOUNT="/media/usbdrive"

mount "${PARTITION}" "${MOUNT}"
if false; then
  lsblk "${DRIVE}"
  parted "${DRIVE}" --script mklabel gpt
  parted -a optimal "${DRIVE}" --script mkpart primary 0% 100%
  parted "${DRIVE}" --script set 1 msftdata on
  mkfs.exfat -n "${LABEL}" "${PARTITION}"
  lsblk "${PARTITION}"
  mount "${PARTITION}" "${MOUNT}"
fi
find "${MOUNT}" -type f -name '*.mkv'

for host in mad max may meg; do
  scp "/Users/graham/Code/asystem/src/meg_may_max_mad/media/src/main/python/rsync/programs/media_"* root@macmini-${host}:/tmp
done

INDEX="4"
rm -rf /tmp/media.log
chmod +x /tmp/media_${INDEX}.sh
nohup /tmp/media_${INDEX}.sh >/tmp/media.log 2>&1 &
disown
tail -f /tmp/media.log

for i in {0..900}; do
  killall -v -9 rsync
  sleep 0.25
done
