#!/bin/sh

NAME=homeassistant
HOME=/home/asystem/${NAME}
INSTALL=/var/lib/asystem/install/$(hostname)/${NAME}/$VERSION_ABSOLUTE
HOST=$(/usr/sbin/ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep '192.168.1')

cd ${INSTALL}
mkdir -p ${HOME}
cp -rvf $(find config -mindepth 1) ${HOME}
docker stop ${NAME} 2>&1 >/dev/null && docker wait ${NAME} 2>&1 >/dev/null && docker system prune --volumes -f
DATA_DIR=${HOME} LOCAL_IP=${HOST} docker-compose --no-ansi up --force-recreate -d
