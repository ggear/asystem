#!/bin/bash

/root/install/media/latest/config/import.sh
for SHARE_DIR in $(grep /share /etc/fstab | grep ext4 | awk 'BEGIN{FS=OFS=" "}{print $2}'); do
  echo python3 /root/install/media/latest/config/rename.py ${SHARE_DIR}/tmp
done
/root/install/media/latest/config/normalise.sh
