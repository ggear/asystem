#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")/mqtt"

. "$ROOT_DIR/../../.env"

printf "\nEntity Metadata publish script [zigbee2mqtt] dropping discovery topics on [$VERNEMQ_SERVICE]:\n"
mosquitto_sub -h $VERNEMQ_SERVICE -p $VERNEMQ_API_PORT -F '%t' -t "homeassistant/#" -W 5 2>/dev/null | sort -u |
  while read topic; do
    base=$(basename "$(dirname "$(dirname "$topic")")")
    if [[ "$base" == 0x* ]] || [[ "$base" == 122* ]]; then
      echo "$topic"
      mosquitto_pub -h $VERNEMQ_SERVICE -p $VERNEMQ_API_PORT -t "$topic" -r -n
    fi
  done
mosquitto_sub -h $VERNEMQ_SERVICE -p $VERNEMQ_API_PORT -F '%t' -t "homeassistant/#" -W 5 2>/dev/null | sort -u |
  while read topic; do
    base=$(basename "$(dirname "$(dirname "$topic")")")
    if [[ "$base" == 0x* ]] || [[ "$base" == 122* ]]; then
      mosquitto_sub -h $VERNEMQ_SERVICE -p $VERNEMQ_API_PORT --remove-retained -F '%t' -t "$topic" -W 1 2>/dev/null
    fi
  done

printf "\nEntity Metadata publish script [zigbee2mqtt] sleeping before dropping data topics ... " && sleep 2 && printf "done\n\n"

printf "Entity Metadata publish script [zigbee2mqtt] dropping data topics on [$VERNEMQ_SERVICE]:\n"
mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_API_PORT} --remove-retained -F '%t' -t 'zigbee/#' -W 1 2>/dev/null

printf "\nEntity Metadata publish script [zigbee2mqtt] sleeping before publishing discovery and data topics ... " && sleep 2 && printf "done\n\n"
