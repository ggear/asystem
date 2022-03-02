#!/bin/sh

HOST=$(basename $(dirname $PWD))
HOME=$(ssh root@${HOST} "find /home/asystem/homeassistant -maxdepth 1 -mindepth 1 ! -name latest 2>/dev/null | sort | tail -n 1")
INSTALL=$(ssh root@${HOST} "find /var/lib/asystem/install/${HOST}/homeassistant -maxdepth 1 -mindepth 1 ! -name latest ! -name latest 2>/dev/null | sort | tail -n 1")

scp -r $PWD/src/main/resources/config/* root@${HOST}:${HOME}
ssh root@${HOST} "cd ${INSTALL} && docker-compose --compatibility restart" 2>/dev/null
