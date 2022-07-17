#!/bin/sh

ROOT_DIR="$(
  cd -- "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)/mqtt"

echo "Entity Metadata publish script dropping topics:"
mosquitto_sub -h ${VERNEMQ_HOST} -p ${VERNEMQ_PORT} --remove-retained -F '%t' -t 'weewx/#' -W 1 2>/dev/null
mosquitto_sub -h ${VERNEMQ_HOST} -p ${VERNEMQ_PORT} --remove-retained -F '%t' -t 'haas/entity/sensor/weewx/#' -W 1 2>/dev/null
echo "Entity Metadata publish script dropping topics complete"

echo "Entity Metadata publish script sleeping before publishing ... " && sleep 1

echo "Entity Metadata publish script publishing topics:"
find ${ROOT_DIR} -name "*.json" -print0 | while read -d $'\0' METADATA_FILE; do
  METADATA_TOPIC=$(dirname "${METADATA_FILE/${ROOT_DIR}\//}")
  mosquitto_pub -h ${VERNEMQ_HOST} -p ${VERNEMQ_PORT} -t ${METADATA_TOPIC} -f ${METADATA_FILE} -r
  echo "${METADATA_TOPIC}"
done
echo "Entity Metadata publish script publishing topics complete"
