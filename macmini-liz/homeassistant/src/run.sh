#!/bin/sh

SERVICE_NAME=homeassistant
SERVICE_HOME=/home/asystem/${SERVICE_NAME}
SERVICE_INSTALL=/var/lib/asystem/install/$(hostname)/${SERVICE_NAME}/$VERSION_ABSOLUTE
SERVICE_HOST_IP=$(/usr/sbin/ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep '192.168.1')

cd ${SERVICE_INSTALL}
mkdir -p ${SERVICE_HOME}
cp -rvf $(find config -mindepth 1) ${SERVICE_HOME}
docker stop ${SERVICE_NAME} 2>&1 >/dev/null && docker wait ${SERVICE_NAME} 2>&1 >/dev/null && docker system prune --volumes -f
DATA_DIR=${SERVICE_HOME} LOCAL_IP=${SERVICE_HOST_IP} docker-compose --no-ansi up --force-recreate -d
