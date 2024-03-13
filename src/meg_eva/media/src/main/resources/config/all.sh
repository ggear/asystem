#!/bin/bash

/root/install/media/latest/config/import.sh /share/2/tmp
for SHARE_DIR in $(grep /share /etc/fstab | grep ext4 | awk 'BEGIN{FS=OFS=" "}{print $2}'); do
  python3 /root/install/media/latest/config/rename.py ${SHARE_DIR}/tmp
  /root/install/media/latest/config/normalise.sh ${SHARE_DIR}
done
/root/install/media/latest/config/library.sh
echo "Storage status:" && df -h $(grep /share /etc/fstab | grep ext4 | awk 'BEGIN{FS=OFS=" "}{print $2}' | tr '\n' ' ')
