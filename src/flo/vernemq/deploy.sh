#!/bin/sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

export $(xargs <${ROOT_DIR}/.env)

printf "Entity Metadata publish script dropping topics:\n"
mosquitto_sub -h ${VERNEMQ_IP_PROD} -p ${VERNEMQ_PORT} --remove-retained -F '%t' -t '#' -W 1 2>/dev/null
printf "Entity Metadata publish script dropping topics complete\n\n"

printf "Entity Metadata publish script sleeping before publishing ... " && sleep 2 && printf "done\n\n"

${ROOT_DIR}/../../lia/weewx/deploy.sh
${ROOT_DIR}/../../meg/tasmota/deploy.sh
${ROOT_DIR}/../../lia/digitemp/deploy.sh
${ROOT_DIR}/../../meg/internet/deploy.sh
${ROOT_DIR}/../../meg_flo_lia/monitor/deploy.sh
${ROOT_DIR}/../../meg_flo_lia/supervise/deploy.sh
${ROOT_DIR}/../../lia/zigbee2mqtt/deploy.sh
