#!/bin/sh

echo "Entity Metadata publish script dropping topics ..."
mosquitto_sub -h ${VERNEMQ_HOST} -p ${VERNEMQ_PORT} --remove-retained -F '%t' -t 'zigbee/#' -W 1 2>/dev/null
mosquitto_sub -h ${VERNEMQ_HOST} -p ${VERNEMQ_PORT} -F '%t' -t 'haas/entity/#' -W 1 2> /dev/null | while read METADATA_TOPIC; do
  [[ $(basename $(dirname $(dirname ${METADATA_TOPIC}))) == 0x* ]] && echo ${METADATA_TOPIC} && mosquitto_pub -h ${VERNEMQ_HOST} -p ${VERNEMQ_PORT} -t "${METADATA_TOPIC}" -n -r
done
echo "Entity Metadata publish script dropping topics complete"

echo "Entity Metadata publish script sleeping before publishing ... " && sleep 2
