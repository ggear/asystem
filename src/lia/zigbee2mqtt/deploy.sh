#!/bin/sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

export $(xargs <${ROOT_DIR}/.env) 2>/dev/null

HOME="/home/asystem/$(basename "${ROOT_DIR}")/latest"
INSTALL="/var/lib/asystem/install/$(basename "${ROOT_DIR}")/latest"
HOST="$(grep "$(basename "$(dirname "${ROOT_DIR}")")" "${ROOT_DIR}/../../../.hosts" | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')"-"$(basename "$(dirname "${ROOT_DIR}")")"
export VERNEMQ_SERVICE=${VERNEMQ_SERVICE_PROD}

${ROOT_DIR}/src/main/resources/config/mqtt.sh
scp -r ${ROOT_DIR}/src/main/resources/config/devices.yaml ${ROOT_DIR}/src/main/resources/config/groups.yaml root@${HOST}:${HOME}
ssh root@${HOST} "cd ${INSTALL} && docker compose --compatibility restart"
if [ $? -eq 0 ]; then

  # INFO: Uncomment to flush all device state
  # ${ROOT_DIR}/src/main/resources/config/mqtt_config_clean.sh

  ${ROOT_DIR}/src/main/resources/config/mqtt_config.sh
fi
