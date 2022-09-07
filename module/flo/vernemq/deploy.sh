#!/bin/sh

ROOT_DIR="$(
  cd -- "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

export $(xargs <${ROOT_DIR}/.env)

echo "Entity Metadata publish script dropping topics ..."
mosquitto_sub -h ${VERNEMQ_IP_PROD} -p ${VERNEMQ_PORT} --remove-retained -F '%t' -t '#' -W 1 2>/dev/null
echo "Entity Metadata publish script dropping topics complete"

echo "Entity Metadata publish script sleeping before publishing ... " && sleep 2

${ROOT_DIR}/../../liz/weewx/deploy.sh
${ROOT_DIR}/../../nel/zigbee2mqtt/deploy.sh
