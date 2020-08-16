#!/bin/sh

cd /var/lib/asystem/install/$(hostname)/homeassistant/$VERSION_ABSOLUTE
mkdir -p /home/asystem/homeassistant
cp -rvf $(find config -mindepth 1) /home/asystem/homeassistant
#docker stop homeassistant 2>&1 >/dev/null && docker wait homeassistant 2>&1 >/dev/null && docker system prune --volumes -f
DATA_DIR=/home/asystem/homeassistant \
  LOCAL_IP=$(/usr/sbin/ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep '192.168.1') \
  docker-compose --no-ansi up --force-recreate -d
