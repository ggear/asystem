#!/bin/sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

export $(xargs <${ROOT_DIR}/.env)

printf "Entity Metadata publish script dropping topics:\n"
mosquitto_sub -h ${VERNEMQ_IP_PROD} -p ${VERNEMQ_PORT} --remove-retained -F '%t' -t '#' -W 1 2>/dev/null
printf "Entity Metadata publish script dropping topics complete\n\n"

printf "Entity Metadata publish script sleeping before publishing ... " && sleep 2 && printf "done\n\n"

${ROOT_DIR}/../../*/weewx/deploy.sh
${ROOT_DIR}/../../*/tasmota/deploy.sh
${ROOT_DIR}/../../*/digitemp/deploy.sh
${ROOT_DIR}/../../*/internet/deploy.sh
${ROOT_DIR}/../../*/monitor/deploy.sh
${ROOT_DIR}/../../*/supervise/deploy.sh
${ROOT_DIR}/../../*/zigbee2mqtt/deploy.sh
