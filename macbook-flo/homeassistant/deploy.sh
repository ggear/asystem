#!/bin/sh

HOSTS_STRING=$(basename $(dirname $(pwd)))
HOSTS_ARRAY=(${HOSTS_STRING//_/ })
HOST=$(basename $(dirname $PWD))
HOME=$(ssh root@${HOST} "find /home/asystem/homeassistant -maxdepth 1 -mindepth 1 ! -name latest 2>/dev/null | sort | tail -n 1")
INSTALL=$(ssh root@${HOST} "find /var/lib/asystem/install/${HOST}/homeassistant -maxdepth 1 -mindepth 1 ! -name latest ! -name latest 2>/dev/null | sort | tail -n 1")

# TODO: Fix
#ssh root@${HOST} "rm -rf ${HOME}/custom_components && rm -rf ${HOME}/custom_packages && rm -rf ${HOME}/ui-lovelace && rm -rf ${HOME}/www"

scp -r $PWD/src/main/resources/config/* root@${HOST}:${HOME}
ssh root@${HOST} "cd ${INSTALL} && docker-compose --compatibility restart" 2>/dev/null
