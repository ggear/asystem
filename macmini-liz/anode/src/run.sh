#!/bin/sh

mkdir -p /home/asystem/anode
cp -rf \
  /var/lib/asystem/install/$VERSION_ABSOLUTE/macmini-liz/anode/.profile \
  /var/lib/asystem/install/$VERSION_ABSOLUTE/macmini-liz/anode/anode.yaml \
  /home/asystem/anode
docker image load -i /var/lib/asystem/install/$VERSION_ABSOLUTE/macmini-liz/anode/anode-$VERSION_ABSOLUTE.tar.gz
docker stop anode 2>&1 >/dev/null && docker wait anode 2>&1 >/dev/null
VERSION=$VERSION_ABSOLUTE \
  DATA_DIR=/home/asystem/anode \
  LOCAL_IP=$(/usr/sbin/ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep '192.168.1') \
  docker-compose -f /var/lib/asystem/install/$VERSION_ABSOLUTE/macmini-liz/anode/docker-compose.yml --no-ansi up --force-recreate -d
docker system prune --volumes -f
