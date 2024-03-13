#!/bin/bash

/root/install/media/latest/config/import.sh /share/2/tmp
for SHARE_DIR in $(grep /share /etc/fstab | grep ext4 | awk 'BEGIN{FS=OFS=" "}{print $2}'); do
  python3 /root/install/media/latest/config/rename.py ${SHARE_DIR}/tmp
  /root/install/media/latest/config/normalise.sh ${SHARE_DIR}
  /root/install/media/latest/config/metadata.sh ${SHARE_DIR}
done
find /share -type f -path *__RENAMED* ! -name .DS_Store
echo "Storage status:" && df -h $(grep /share /etc/fstab | grep ext4 | awk 'BEGIN{FS=OFS=" "}{print $2}' | tr '\n' ' ')
