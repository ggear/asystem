#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

ROOT_DIR="$(dirname $(readlink -f "$0"))/mqtt"

. ${ROOT_DIR}/../../.env

printf "\nEntity Metadata publish script [supervisor] dropping discovery topics:\n"
mosquitto_sub -h $VERNEMQ_SERVICE_PROD -p $VERNEMQ_API_PORT -F '%t' -t "homeassistant/+/supervisor_${SUPERVISOR_HOST}/+/config" -W 10 2>/dev/null |   while read topic; do
    echo "Destroying: $topic"
    mosquitto_pub -h $VERNEMQ_SERVICE_PROD -p $VERNEMQ_API_PORT -t "$topic" -r -n
  done
mosquitto_sub -h $VERNEMQ_SERVICE_PROD -p $VERNEMQ_API_PORT --remove-retained -F '%t' -t "homeassistant/+/supervisor_${SUPERVISOR_HOST}/+/config" -W 30 2>/dev/null

printf "\nEntity Metadata publish script [supervisor] sleeping before dropping data topics ... " && sleep 2 && printf "done\n\n"

printf "Entity Metadata publish script [supervisor] dropping data topics:\n"
mosquitto_sub -h $VERNEMQ_SERVICE_PROD -p $VERNEMQ_API_PORT -F '%t' -t "supervisor/${SUPERVISOR_HOST}/data/+/+/+" -W 10 2>/dev/null |   while read topic; do
    echo "Destroying: $topic"
    mosquitto_pub -h $VERNEMQ_SERVICE_PROD -p $VERNEMQ_API_PORT -t "$topic" -r -n
  done
mosquitto_sub -h $VERNEMQ_SERVICE_PROD -p $VERNEMQ_API_PORT --remove-retained -F '%t' -t "supervisor/${SUPERVISOR_HOST}/data/+/+/+" -W 30 2>/dev/null

printf "\nEntity Metadata publish script [supervisor] sleeping before publishing discovery topics ... " && sleep 2 && printf "done\n\n"

printf "Entity Metadata publish script [supervisor] publishing discovery topics:\n"
find $ROOT_DIR -path "*/supervisor_${SUPERVISOR_HOST}/*" -name "*.json" -print0 | while read -d $'\0' METADATA_FILE; do
  METADATA_TOPIC=$(dirname "${METADATA_FILE/$ROOT_DIR\//}")
  mosquitto_pub -h $VERNEMQ_SERVICE -p $VERNEMQ_API_PORT -t $METADATA_TOPIC -f $METADATA_FILE -r
  printf "$METADATA_TOPIC\n"
done
printf "\n"