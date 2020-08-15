#!/bin/sh

cd /var/lib/asystem/install/$VERSION_ABSOLUTE/$(hostname)/vernemq
mkdir -p /home/asystem/vernemq
DATA_DIR=/home/asystem/vernemq \
  LOCAL_IP=$(/usr/sbin/ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep '192.168.1') \
  docker-compose --no-ansi up --force-recreate -d
