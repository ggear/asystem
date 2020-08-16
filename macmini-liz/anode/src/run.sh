#!/bin/sh

cd /var/lib/asystem/install/$(hostname)/anode/$VERSION_ABSOLUTE
mkdir -p /home/asystem/anode
cp -rvf $(find ./* ! -name run.sh) /home/asystem/anode
docker image load -i anode-$VERSION_ABSOLUTE.tar.gz
docker stop anode 2>&1 >/dev/null && docker wait anode 2>&1 >/dev/null
VERSION=$VERSION_ABSOLUTE \
  DATA_DIR=/home/asystem/anode \
  LOCAL_IP=$(/usr/sbin/ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep '192.168.1') \
  docker-compose --no-ansi up --force-recreate -d
