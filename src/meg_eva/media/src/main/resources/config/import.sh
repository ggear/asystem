#!/bin/bash

SHARE_DIR=${1}
if [ ! -d "${SHARE_DIR}" ]; then
  echo "Usage: ${0} <media-tmp-dir>"
  exit 1
fi
if [ $(lsblk -ro name,label | grep GRAHAM | wc -l) -eq 1 ]; then
  IMPORT_MEDIA_DEV="/dev/"$(lsblk -ro name,label | grep GRAHAM | awk 'BEGIN{FS=OFS=" "}{print $1}')
  if [ -a ${IMPORT_MEDIA_DEV} ]; then
    echo "Starting copy of [/media/usbdrive] from [${IMPORT_MEDIA_DEV}] to [${SHARE_DIR}]"
    mkdir -p /media/usbdrive
    umount -fq /media/usbdrive
    mount -t exfat ${IMPORT_MEDIA_DEV} /media/usbdrive
    rm -rf /media/usbdrive/.Spotlight-V100 /media/usbdrive/.Trashes /media/usbdrive/.fseventsd /media/usbdrive/System\ Volume\ Information /media/usbdrive/\$RECYCLE.BIN
    rsync -avP /media/usbdrive ${SHARE_DIR}
    rm -rf ${SHARE_DIR}/usbdrive/..?* ${SHARE_DIR}/usbdrive/.[!.]*
    umount -fq /media/usbdrive
    echo "Completed copy of [/media/usbdrive] from [${IMPORT_MEDIA_DEV}] to [${SHARE_DIR}]"
  fi
fi
exit 0
