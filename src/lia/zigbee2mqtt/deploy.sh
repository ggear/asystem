#!/bin/sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

export $(xargs <${ROOT_DIR}/.env) 2>/dev/null

HOST="$(grep $(basename $(dirname ${ROOT_DIR})) ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-$(basename $(dirname ${ROOT_DIR}))"
HOME=$(ssh root@${HOST} "find /home/asystem/$(basename ${ROOT_DIR}) -maxdepth 1 -mindepth 1 ! -name latest 2>/dev/null | sort | tail -n 1")
INSTALL=$(ssh root@${HOST} "find /var/lib/asystem/install/$(basename ${ROOT_DIR}) -maxdepth 1 -mindepth 1 ! -name latest ! -name latest 2>/dev/null | sort | tail -n 1")
export VERNEMQ_SERVICE=${VERNEMQ_SERVICE_PROD}

${ROOT_DIR}/src/main/resources/config/mqtt.sh
scp -r ${ROOT_DIR}/src/main/resources/config/devices.yaml root@${HOST}:${HOME}
scp -r ${ROOT_DIR}/src/main/resources/config/groups.yaml root@${HOST}:${HOME}
ssh root@${HOST} "cd ${INSTALL} && docker compose --compatibility restart"
if [ $? -eq 0 ]; then

  # NOTE: Uncomment to flush all device state
  # ${ROOT_DIR}/src/main/resources/config/mqtt_config_clean.sh

  ${ROOT_DIR}/src/main/resources/config/mqtt_config.sh
fi
