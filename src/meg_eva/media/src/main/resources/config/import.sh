#!/bin/bash

IMPORT_MEDIA_SHARE=/share/3/tmp

if [ $(lsblk -ro name,label | grep GRAHAM | wc -l) -eq 1 ]; then
  IMPORT_MEDIA_DEV="/dev/"$(lsblk -ro name,label | grep GRAHAM | awk 'BEGIN{FS=OFS=" "}{print $1}')
  if [ -a ${IMPORT_MEDIA_DEV} ]; then
    echo "Starting copy of [/media/usbdrive] from [${IMPORT_MEDIA_DEV}] to [${IMPORT_MEDIA_SHARE}]"
    mkdir -p /media/usbdrive
    umount -fq /media/usbdrive
    mount -t exfat ${IMPORT_MEDIA_DEV} /media/usbdrive
    find /media/usbdrive -name "\.*" -exec rm {} \;
    rm -rf /media/usbdrive/\.* /media/usbdrive/System* /media/usbdrive/\$RECYCLE.BIN
    rsync -avP /media/usbdrive ${IMPORT_MEDIA_SHARE}
    umount -fq /media/usbdrive
    echo "Completed copy of [/media/usbdrive] from [${IMPORT_MEDIA_DEV}] to [${IMPORT_MEDIA_SHARE}]"
  fi
fi
