#!/bin/sh

DATA_DIR=/home/asystem/vernemq \
  LOCAL_IP=$(/usr/sbin/ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep '192.168.1') \
  docker-compose -f /var/lib/asystem/install/$VERSION_ABSOLUTE/macmini-liz/vernemq/docker-compose.yml --no-ansi up --force-recreate -d
