#!/bin/sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

for MQTT_SCRIPT in $(find ""${ROOT_DIR}/../.."" -name certs.sh -type f -path "*src*"); do
  DEPLOY_SCRIPT="$(dirname "${MQTT_SCRIPT}")/../../../../deploy.sh"
  if [ -f "${DEPLOY_SCRIPT}" ]; then
    echo "" &&
      echo "----------------------------------------------------------------------------------------------------" &&
      echo "Executing deploy script [$(realpath ${DEPLOY_SCRIPT})]" &&
      echo "----------------------------------------------------------------------------------------------------" &&
      echo "" && ${DEPLOY_SCRIPT}
  fi
done
