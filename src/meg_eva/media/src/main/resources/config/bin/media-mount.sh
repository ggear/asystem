#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. "${ROOT_DIR}/.env_media"

echo -n "Mounting '${SHARE_ROOT}' ... "
if [ $(uname) == "Darwin" ]; then
  for _SHARE in macmini-eva,1 macmini-eva,2 macmini-eva,3 macmini-meg,4 macmini-meg,5; do
    IFS=","
    set -- ${_SHARE}
    mkdir -p ~/Desktop/share/${2}
    diskutil unmount force ~/Desktop/share/${2} 2>&1 >/dev/null
    mount_smbfs //GUEST:@${1}/share-${2} ~/Desktop/share/${2}
  done
else
  umount -fq /media/usbdrive
  mount -t exfat "/dev/"$(lsblk -ro name,label | grep GRAHAM | awk 'BEGIN{FS=OFS=" "}{print $1}') /media/usbdrive
fi
echo "done"
