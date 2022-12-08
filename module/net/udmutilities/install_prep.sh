#!/bin/sh

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/${SERVICE_VERSION_ABSOLUTE}

cd ${SERVICE_INSTALL} || exit

mkdir -p /mnt/data/asystem
#if [[ ! -L /var/lib/asystem ]]; then
#  if [[ -d /var/lib/asystem ]]; then
#    mv /var/lib/asystem/* /mnt/data/asystem
#    rm -r /mnt/data/asystem
#  fi
#  ln -s /mnt/data/asystem /var/lib/asystem
#fi
#cp -rvf /mnt/data/asystem/* /var/lib/asystem
