#!/bin/sh

SERVICE_NAME=homeassistant
SERVICE_HOME=/home/asystem/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_HOME_OLD=$(ls -dt $(dirname ${SERVICE_HOME})/*/ 2>/dev/null | head -n 1)
SERVICE_HOME_OLDEST=$(ls -dt $(dirname ${SERVICE_HOME})/*/ 2>/dev/null | tail -n -$(($(ls -dt $(dirname ${SERVICE_HOME})/*/ 2>/dev/null | wc -l) - 1)) 2>/dev/null)
SERVICE_INSTALL=/var/lib/asystem/install/$(hostname)/${SERVICE_NAME}/${VERSION_ABSOLUTE}
SERVICE_HOST_IP=$(/usr/sbin/ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep '192.168.1')

[ -d "/var/lib/asystem/install" ] &&
  [ -d "$(ls -td /var/lib/asystem/install/udm-rack*/host/* | head -1)" ] &&
  [ -f "$(ls -td /var/lib/asystem/install/udm-rack*/host/* | head -1)/run.sh" ] &&
  cp -rvf "$(ls -td /var/lib/asystem/install/udm-rack*/host/* | head -1)/run.sh" /mnt/data/on_boot.d/keys.sh
