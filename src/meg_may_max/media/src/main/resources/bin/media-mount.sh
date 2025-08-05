#!/usr/bin/env bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

. "${ROOT_DIR}/.env_media"

if [ $(hostname) == "macbook-lyn" ]; then
  hosts_file=$(realpath "${LIB_ROOT}/../../../../../../../.hosts")
  for fstab_file in $(find "${LIB_ROOT}/../../../../../.." ! -path '*/target/*' -name fstab | sort); do
    host_label=$(basename $(realpath "${fstab_file}/../../../../.."))
    host_name="$(grep "^${host_label}=" "${hosts_file}" | cut -d'=' -f2 | cut -d',' -f1)-${host_label}"
    for share_index in $(grep -v '^#' ${fstab_file} | awk '/\/share/ && /ext4/ {print $2}' | sed 's|/share/||'); do
      share_dir="${HOME}/Desktop/share/${share_index}"
      share_samba="//GUEST:@${host_name}/share-${share_index}"
      echo -n "Mounting ${share_samba} ... "
      mkdir -p ${share_dir}
      diskutil unmount force ${share_dir} &>/dev/null
      mount_smbfs -o soft,nodatacache,nodatacache ${share_samba} ${share_dir} && echo "done"
    done
  done
else
  IMPORT_MEDIA_DEV="/dev/"$(lsblk -ro name,label | grep GRAHAM | awk 'BEGIN{FS=OFS=" "}{print $1}')
  umount -fq /media/usbdrive 2>&1 >/dev/null
  mount -t exfat ${IMPORT_MEDIA_DEV} /media/usbdrive
fi
