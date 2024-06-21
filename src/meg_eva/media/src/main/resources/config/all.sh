#!/bin/bash

SHARE_DIRS=$(grep /share /etc/fstab | grep ext4 | awk 'BEGIN{FS=OFS=" "}{print $2}')

/root/install/media/latest/config/import.sh /share/2/tmp
for SHARE_DIR in ${SHARE_DIRS}; do /root/install/media/latest/config/normalise.sh ${SHARE_DIR}; done
for SHARE_DIR in ${SHARE_DIRS}; do python3 /root/install/media/latest/config/rename.py ${SHARE_DIR}/tmp; done
for SHARE_DIR in ${SHARE_DIRS}; do python3 /root/install/media/latest/config/analyse.py ${SHARE_DIR}/media; done
/root/install/media/latest/config/library.sh
echo "Storage status ... done" && df -h $(echo ${SHARE_DIRS} | tr '\n' ' ') | cut -c 40-
