#!/bin/sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

HOSTS=$(echo $(basename $(dirname $(pwd))) | tr "_" "\n")

export $(xargs <${ROOT_DIR}/.env)

export VERNEMQ_IP=${VERNEMQ_IP_PROD}

${ROOT_DIR}/src/main/resources/config/mqtt.sh

printf "Entity Metadata publish script [monitor] sleeping before publishing data topics ... " && sleep 2 && printf "done\n\nEntity Metadata publish script [monitor] publishing data topics:\n"

for HOST in ${HOSTS}; do
  HOST="$(grep ${HOST} ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-${HOST}"
  printf "Entity Metadata publish script publishing data on [${HOST}]:\n"
  ssh -o StrictHostKeyChecking=no root@${HOST} "docker exec monitor telegraf --debug --once"
  printf "\n"
done
