#!/bin/sh

ROOT_DIR="$(
  cd -- "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

export $(xargs <${ROOT_DIR}/.env)

HOST="$(grep $(basename $(dirname ${ROOT_DIR})) ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-$(basename $(dirname ${ROOT_DIR}))"
HOME=$(ssh root@${HOST} "find /home/asystem/$(basename ${ROOT_DIR}) -maxdepth 1 -mindepth 1 ! -name latest 2>/dev/null | sort | tail -n 1")
INSTALL=$(ssh root@${HOST} "find /var/lib/asystem/install/$(basename ${ROOT_DIR}) -maxdepth 1 -mindepth 1 ! -name latest ! -name latest 2>/dev/null | sort | tail -n 1")
export VERNEMQ_IP=${VERNEMQ_IP_PROD}

#${ROOT_DIR}/src/main/resources/config/mqtt.sh
scp -r ${ROOT_DIR}/src/main/resources/config/* root@${HOST}:${HOME}
ssh root@${HOST} "cd ${INSTALL} && docker-compose --compatibility restart"
[ $? -eq 0 ] && ${ROOT_DIR}/src/main/resources/config/mqtt_config.sh
