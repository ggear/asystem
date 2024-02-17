#!/bin/bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit

chmod +x config/*.sh

for SHARE_DIR in $(grep /share /etc/fstab | grep ext4 | awk 'BEGIN{FS=OFS=" "}{print $2}'); do
  for SHARE_DIR_SCOPE in "kids" "parents"; do
    for SHARE_DIR_MEDIA in "audio" "movies" "series"; do
      mkdir -p ${SHARE_DIR}/media/${SHARE_DIR_SCOPE}/${SHARE_DIR_MEDIA}
    done
  done
done
