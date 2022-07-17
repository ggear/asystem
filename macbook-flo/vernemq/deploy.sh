#!/bin/sh

ROOT_DIR="$(
  cd -- "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

export $(xargs <${ROOT_DIR}/.env)

mosquitto_sub -h ${VERNEMQ_IP_PROD} -p ${VERNEMQ_PORT} --remove-retained -t '#' -W 1 2>/dev/null

${ROOT_DIR}/../../macmini-liz/weewx/deploy.sh
${ROOT_DIR}/../../macmini-nel/zigbee2mqtt/deploy.sh
