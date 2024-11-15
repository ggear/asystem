#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. "${ROOT_DIR}/.env_media"

if [ $(uname) == "Darwin" ]; then
  for _SHARE in macmini-eva,1 macmini-eva,2 macmini-eva,3 macmini-meg,4 macmini-meg,5; do
    IFS=","
    set -- ${_SHARE}
    mkdir -p ~/Desktop/share/${2}
    diskutil unmount force ~/Desktop/share/${2} &>/dev/null
    mount_smbfs //GUEST:@${1}/share-${2} ~/Desktop/share/${2}
  done
else
  IMPORT_MEDIA_DEV="/dev/"$(lsblk -ro name,label | grep GRAHAM | awk 'BEGIN{FS=OFS=" "}{print $1}')
  umount -fq /media/usbdrive 2>&1 >/dev/null
  mount -t exfat ${IMPORT_MEDIA_DEV} /media/usbdrive
fi
