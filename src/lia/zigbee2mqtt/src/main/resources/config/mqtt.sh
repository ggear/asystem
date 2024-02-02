#!/bin/sh

ROOT_DIR="$(dirname $(readlink -f "$0"))/mqtt"

printf "\nEntity Metadata publish script [zigbee2mqtt] dropping discovery topics:\n"
mosquitto_sub -h ${VERNEMQ_HOST} -p ${VERNEMQ_PORT} -F '%t' -t 'homeassistant/#' -W 1 2>/dev/null | while read METADATA_TOPIC; do
  ([[ $(basename $(dirname $(dirname ${METADATA_TOPIC}))) == 0x* ]] || [[ $(basename $(dirname $(dirname ${METADATA_TOPIC}))) == 122* ]]) && printf "${METADATA_TOPIC}\n" && mosquitto_pub -h ${VERNEMQ_HOST} -p ${VERNEMQ_PORT} -t "${METADATA_TOPIC}" -n -r
done

printf "\nEntity Metadata publish script [zigbee2mqtt] sleeping before dropping data topics ... " && sleep 2 && printf "done\n\n"

printf "Entity Metadata publish script [zigbee2mqtt] dropping data topics:\n"
mosquitto_sub -h ${VERNEMQ_HOST} -p ${VERNEMQ_PORT} --remove-retained -F '%t' -t 'zigbee/#' -W 1 2>/dev/null

printf "\nEntity Metadata publish script [zigbee2mqtt] sleeping before publishing discovery and data topics ... " && sleep 2 && printf "done\n\n"
