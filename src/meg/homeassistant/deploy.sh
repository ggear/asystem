#!/bin/sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

HOST="$(grep $(basename $(dirname ${ROOT_DIR})) ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-$(basename $(dirname ${ROOT_DIR}))"
HOME=$(ssh root@${HOST} "find /home/asystem/$(basename ${ROOT_DIR}) -maxdepth 1 -mindepth 1 ! -name latest 2>/dev/null | sort | tail -n 1")
INSTALL=$(ssh root@${HOST} "find /var/lib/asystem/install/$(basename ${ROOT_DIR}) -maxdepth 1 -mindepth 1 ! -name latest ! -name latest 2>/dev/null | sort | tail -n 1")

ssh root@${HOST} "rm -rf ${HOME}/custom_components && rm -rf ${HOME}/custom_packages && rm -rf ${HOME}/ui-lovelace && rm -rf ${HOME}/www"
scp -r ${ROOT_DIR}/src/main/resources/config/* root@${HOST}:${HOME}
ssh root@${HOST} "cd ${INSTALL} && docker compose --compatibility restart"
