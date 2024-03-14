#!/bin/sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

export $(xargs <${ROOT_DIR}/.env)

printf "\nEntity Metadata publish script [vernemq] dropping topics:\n"
mosquitto_sub -h ${VERNEMQ_SERVICE_PROD} -p ${VERNEMQ_PORT} --remove-retained -F '%t' -t '#' -W 1 2>/dev/null

printf "\nEntity Metadata publish script [vernemq] sleeping before publishing discovery and data topics ... " && sleep 2 && printf "done\n\n"

#for MQTT_SCRIPT in $(find ""${ROOT_DIR}/../.."" -name mqtt.sh -type f -path "*src*"); do
#  DEPLOY_SCRIPT="$(dirname "${MQTT_SCRIPT}")/../../../../deploy.sh"
#  if [ -f "${DEPLOY_SCRIPT}" ]; then
#    echo "" &&
#      echo "----------------------------------------------------------------------------------------------------" &&
#      echo "Executing deploy script [$(realpath ${DEPLOY_SCRIPT})]" &&
#      echo "----------------------------------------------------------------------------------------------------" &&
#      echo "" && ${DEPLOY_SCRIPT}
#  fi
#done

echo ""
for MODULE_DIR in $(find "${ROOT_DIR}/../.." -name mqtt.sh -type f -path "*/src/*" ! -path "*/target/*" | sed 's/\/src\/main\// /' | cut -d ' ' -f1); do
  echo "----------------------------------------------------------------------------------------------------" &&
    echo "Executing deploy script for module [$(basename ${MODULE_DIR})] ... " &&
    echo "----------------------------------------------------------------------------------------------------" &&
    echo ""
  "${MODULE_DIR}/generate.sh"
  "${MODULE_DIR}/deploy.sh"
  echo "" && echo "----------------------------------------------------------------------------------------------------" &&
    echo "Executing deploy script for module [$(basename ${MODULE_DIR})] complete" &&
    echo "----------------------------------------------------------------------------------------------------" &&
    echo ""
done
