#!/bin/bash

for SHARE_DIR in $(grep /share /etc/fstab | grep ext4 | awk 'BEGIN{FS=OFS=" "}{print $2}'); do
  echo -n "Normalising ${SHARE_DIR} ... "
  setfacl -bR ${SHARE_DIR}
  find ${SHARE_DIR} -type f -exec chmod 640 {} \;
  find ${SHARE_DIR} -type d -exec chmod 750 {} \;
  find ${SHARE_DIR} -type d -exec chown graham:users {} \;
  find ${SHARE_DIR} -type f -name nohup -exec rm -f {} \;
  find ${SHARE_DIR} -type f -name .DS_Store -exec rm -f {} \;
  echo "done"
done