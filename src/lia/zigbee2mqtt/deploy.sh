#!/bin/sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

export $(xargs <${ROOT_DIR}/.env) 2>/dev/null

HOME="/home/asystem/$(basename "${ROOT_DIR}")/latest"
INSTALL="/var/lib/asystem/install/$(basename "${ROOT_DIR}")/latest"
HOST="$(grep "$(basename "$(dirname "${ROOT_DIR}")")" "${ROOT_DIR}/../../../.hosts" | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')"-"$(basename "$(dirname "${ROOT_DIR}")")"
export VERNEMQ_SERVICE=${VERNEMQ_SERVICE_PROD}


# TODO: Fix me!

#ssh root@${HOST} "cd ${INSTALL}; echo '---' && echo -n 'Stopping container ... ' && docker stop $(basename ${ROOT_DIR}) && echo '---' && sleep 1"
#${ROOT_DIR}/src/main/resources/image/mqtt.sh
#scp -r ${ROOT_DIR}/src/main/resources/data/devices.yaml ${ROOT_DIR}/src/main/resources/data/groups.yaml root@${HOST}:${HOME}
#ssh root@${HOST} "cd ${INSTALL}; echo '---' && echo -n 'Starting container ... ' && docker start $(basename ${ROOT_DIR}) && echo '---' && sleep 1 && docker logs -f $(basename ${ROOT_DIR})"


#if [ $? -eq 0 ]; then
#
#  # INFO: Uncomment to flush all device state
#  # ${ROOT_DIR}/src/main/resources/config/mqtt_config_clean.sh
#
#  ${ROOT_DIR}/src/main/resources/data/mqtt/mqtt_config.sh
#fi


${ROOT_DIR}/src/main/resources/image/mqtt/mqtt_config.sh
