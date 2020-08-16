#!/bin/sh

cd /var/lib/asystem/install/$(hostname)/vernemq/$VERSION_ABSOLUTE
mkdir -p /home/asystem/vernemq
cp -rvf $(find config -mindepth 1) /home/asystem/vernemq
docker stop vernemq 2>&1 >/dev/null && docker wait vernemq 2>&1 >/dev/null && docker system prune --volumes -f
DATA_DIR=/home/asystem/vernemq \
  LOCAL_IP=$(/usr/sbin/ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep '192.168.1') \
  docker-compose --no-ansi up --force-recreate -d
