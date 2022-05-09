#!/bin/bash

ROOT_DIR="$(
  cd -- "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)/../../.."

source "${ROOT_DIR}/.env"
echo "Entity Metadata publish script connecting to [mqtt://${VERNEMQ_HOST_PROD}:${VERNEMQ_PORT}]"

mosquitto_sub -h ${VERNEMQ_HOST_PROD} -p ${VERNEMQ_PORT} -t haas/entity/# -W 1 -v 2>/dev/null | while IFS= read -r LINE; do
  METADATA_TOPIC=$(echo ${LINE} | awk '{print $1}')
  mosquitto_pub -h ${VERNEMQ_HOST_PROD} -p ${VERNEMQ_PORT} -t ${METADATA_TOPIC} -n -r >/dev/null 2>&1 && echo "Entity Metadata publish script flushing the topic [${METADATA_TOPIC}]"
done

echo "Entity Metadata publish script sleeping before publishing ... " && sleep 1

for METADATA_FILE in $(find "${ROOT_DIR}/src/build/resources/entity_metadata" -name "*.json" -type f); do
  METADATA_TOPIC="$(cat ${METADATA_FILE} | jq -r .state_topic)/config"
  mosquitto_pub -h ${VERNEMQ_HOST_PROD} -p ${VERNEMQ_PORT} -t ${METADATA_TOPIC} -f ${METADATA_FILE} -r >/dev/null 2>&1 && echo "Entity Metadata publish script published to topic [${METADATA_TOPIC}]"
done
