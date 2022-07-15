#!/bin/bash

ROOT_DIR="$(
  cd -- "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)/mqtt"

find ${ROOT_DIR} -name "*.json" -print0 | while read -d $'\0' METADATA_FILE; do
  METADATA_TOPIC=$(dirname "${METADATA_FILE/${ROOT_DIR}\//}")
  mosquitto_pub -h ${VERNEMQ_HOST} -p ${VERNEMQ_PORT} -t ${METADATA_TOPIC} -n -r >/dev/null 2>&1 && echo "Entity Metadata publish script dropping topic [${METADATA_TOPIC}]"
done

echo "Entity Metadata publish script sleeping before publishing ... " && sleep 1

find ${ROOT_DIR} -name "*.json" -print0 | while read -d $'\0' METADATA_FILE; do
  METADATA_TOPIC=$(dirname "${METADATA_FILE/${ROOT_DIR}\//}")
  mosquitto_pub -h ${VERNEMQ_HOST} -p ${VERNEMQ_PORT} -t ${METADATA_TOPIC} -f ${METADATA_FILE} -r >/dev/null 2>&1 && echo "Entity Metadata publish script published file [${METADATA_FILE}]"
done
