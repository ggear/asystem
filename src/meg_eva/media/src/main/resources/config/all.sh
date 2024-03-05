#!/bin/bash

/root/install/media/latest/config/import.sh /share/3/tmp
for SHARE_DIR in $(grep /share /etc/fstab | grep ext4 | awk 'BEGIN{FS=OFS=" "}{print $2}'); do
  python3 /root/install/media/latest/config/rename.py ${SHARE_DIR}/tmp
  /root/install/media/latest/config/normalise.sh ${SHARE_DIR}
done
echo  "" && find /share -type f -path *__RENAMED* ! -name .DS_Store
echo  "" && df -h /share/* && echo ""
