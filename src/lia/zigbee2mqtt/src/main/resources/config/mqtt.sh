#!/bin/sh

ROOT_DIR="$(dirname $(readlink -f "$0"))/mqtt"

printf "Entity Metadata publish script dropping topics:\n"
mosquitto_sub -h ${VERNEMQ_IP} -p ${VERNEMQ_PORT} --remove-retained -F '%t' -t 'zigbee/#' -W 1 2>/dev/null
mosquitto_sub -h ${VERNEMQ_IP} -p ${VERNEMQ_PORT} -F '%t' -t 'haas/entity/#' -W 1 2>/dev/null | while read METADATA_TOPIC; do
  ([[ $(basename $(dirname $(dirname ${METADATA_TOPIC}))) == 0x* ]] || [[ $(basename $(dirname $(dirname ${METADATA_TOPIC}))) == 122105* ]]) && printf ${METADATA_TOPIC} && mosquitto_pub -h ${VERNEMQ_IP} -p ${VERNEMQ_PORT} -t "${METADATA_TOPIC}" -n -r
done
printf "Entity Metadata publish script dropping topics complete\n\n"

printf "Entity Metadata publish script sleeping before publishing ... " && sleep 2 && printf "done\n\n"
