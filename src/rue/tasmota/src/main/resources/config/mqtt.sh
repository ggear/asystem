#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

ROOT_DIR="$(dirname "$(readlink -f "$0")")/mqtt"

for f in "$ROOT_DIR/../../.env" "$ROOT_DIR/../../../../.env"; do [ -f "$f" ] && . "$f"; done

printf "\nEntity Metadata publish script [tasmota] dropping discovery topics on [$VERNEMQ_SERVICE]:\n"
mosquitto_sub -h $VERNEMQ_SERVICE -p $VERNEMQ_API_PORT -F '%t' -t "homeassistant/+/tasmota/#" -W 5 2>/dev/null | sort -u | \
  while read topic; do
    echo "$topic"
    mosquitto_pub -h $VERNEMQ_SERVICE -p $VERNEMQ_API_PORT -t "$topic" -r -n
  done
mosquitto_sub -h $VERNEMQ_SERVICE -p $VERNEMQ_API_PORT --remove-retained -F '%t' -t "homeassistant/+/tasmota/#" -W 5 2>/dev/null

printf "\nEntity Metadata publish script [tasmota] sleeping before dropping data topics ... " && sleep 2 && printf "done\n\n"

printf "Entity Metadata publish script [tasmota] dropping data topics on [$VERNEMQ_SERVICE]:\n"
mosquitto_sub -h $VERNEMQ_SERVICE -p $VERNEMQ_API_PORT --remove-retained -F '%t' -t "tasmota/#" -W 1 2>/dev/null

printf "\nEntity Metadata publish script [tasmota/#] sleeping before publishing discovery topics ... " && sleep 2 && printf "done\n\n"

printf "Entity Metadata publish script [tasmota] publishing discovery topics on [$VERNEMQ_SERVICE]:\n"
find "$ROOT_DIR" -path "*/tasmota/*" -name "*.json" -print0 | sort -z | while read -d $'\0' METADATA_FILE; do
  METADATA_TOPIC=$(dirname "${METADATA_FILE/$ROOT_DIR\//}")
  mosquitto_pub -h $VERNEMQ_SERVICE -p $VERNEMQ_API_PORT -t "$METADATA_TOPIC" -f "$METADATA_FILE" -r
  printf "%s\n" "$METADATA_TOPIC"
done
printf "\n"