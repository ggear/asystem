#!/usr/bin/env bash

ROOT_DIR="$(dirname $(readlink -f "$0"))/mqtt"

printf "\nEntity Metadata publish script [digitemp] dropping discovery topics:\n"
mosquitto_sub -h $VERNEMQ_SERVICE -p $VERNEMQ_API_PORT --remove-retained -F '%t' -t 'homeassistant/+/digitemp/#' -W 1 2>/dev/null

printf "\nEntity Metadata publish script [digitemp] sleeping before dropping data topics ... " && sleep 2 && printf "done\n\n"

printf "Entity Metadata publish script [digitemp] dropping data topics:\n"
mosquitto_sub -h $VERNEMQ_SERVICE -p $VERNEMQ_API_PORT --remove-retained -F '%t' -t 'telegraf/+/digitemp/#' -W 1 2>/dev/null

printf "\nEntity Metadata publish script [digitemp] sleeping before publishing discovery topics ... " && sleep 2 && printf "done\n\n"

printf "Entity Metadata publish script [digitemp] publishing discovery topics:\n"
find $ROOT_DIR -name "*.json" -print0 | while read -d $'\0' METADATA_FILE; do
  METADATA_TOPIC=$(dirname "${METADATA_FILE/$ROOT_DIR\//}")
  mosquitto_pub -h $VERNEMQ_SERVICE -p $VERNEMQ_API_PORT -t $METADATA_TOPIC -f $METADATA_FILE -r
  printf "$METADATA_TOPIC\n"
done
printf "\n"