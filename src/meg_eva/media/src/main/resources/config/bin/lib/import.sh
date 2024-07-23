#!/bin/bash

. "${ROOT_DIR}/../.env_media"

WORKING_DIR=${1}
if [ ! -d "${WORKING_DIR}" ]; then
  echo "Usage: ${0} <working-dir>"
  exit 1
fi

if [ $(lsblk -ro name,label | grep GRAHAM | wc -l) -eq 1 ]; then
  IMPORT_MEDIA_DEV="/dev/"$(lsblk -ro name,label | grep GRAHAM | awk 'BEGIN{FS=OFS=" "}{print $1}')
  if [ -a ${IMPORT_MEDIA_DEV} ]; then
    echo "#######################################################################################"
    echo "Starting rsync of /media/usbdrive to ${WORKING_DIR}/tmp"
    echo "#######################################################################################"
    mkdir -p /media/usbdrive
    umount -fq /media/usbdrive
    mount -t exfat ${IMPORT_MEDIA_DEV} /media/usbdrive
    rsync -avP /media/usbdrive ${WORKING_DIR}/tmp
    echo '' && echo "Completed rsync of /media/usbdrive to ${WORKING_DIR}/tmp" && date && echo ''
    echo "#######################################################################################"
  fi
fi
echo -n "Import '${WORKING_DIR}/tmp' ... "
umount -fq /media/usbdrive >/dev/null 2>&1
rm -rf \
  ${WORKING_DIR}/tmp/usbdrive/.Spotlight-V100 \
  ${WORKING_DIR}/tmp/usbdrive/.Trashes \
  ${WORKING_DIR}/tmp/usbdrive/.fseventsd \
  ${WORKING_DIR}/tmp/usbdrive/System\ Volume\ Information \
  ${WORKING_DIR}/tmp/usbdrive/\$RECYCLE.BIN \
  ${WORKING_DIR}/tmp/usbdrive/..?* \
  ${WORKING_DIR}/tmp/usbdrive/.[!.]*
echo "done"
