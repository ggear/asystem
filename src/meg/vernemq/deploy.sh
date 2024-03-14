#!/bin/sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

export $(xargs <${ROOT_DIR}/.env)

printf "\nEntity Metadata publish script [vernemq] dropping topics:\n"
mosquitto_sub -h ${VERNEMQ_SERVICE_PROD} -p ${VERNEMQ_PORT} --remove-retained -F '%t' -t '#' -W 1 2>/dev/null

printf "\nEntity Metadata publish script [vernemq] sleeping before publishing discovery and data topics ... " && sleep 2 && printf "done\n\n"

echo ""
for MODULE_DIR in $(find "${ROOT_DIR}/../.." -name mqtt.sh -type f -path "*/src/*" ! -path "*/target/*" | sed 's/\/src\/main\// /' | cut -d ' ' -f1); do
  echo "----------------------------------------------------------------------------------------------------" &&
    echo "Executing deploy script for module [$(basename ${MODULE_DIR})] starting ... " &&
    echo "----------------------------------------------------------------------------------------------------" &&
    echo ""
  [ -f "${MODULE_DIR}/generate.sh" ] && "${MODULE_DIR}/generate.sh"
  [ -f "${MODULE_DIR}/deploy.sh" ] && "${MODULE_DIR}/deploy.sh"
  echo "" && echo "----------------------------------------------------------------------------------------------------" &&
    echo "Executing deploy script for module [$(basename ${MODULE_DIR})] finished" &&
    echo "----------------------------------------------------------------------------------------------------" &&
    echo ""
done
