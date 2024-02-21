#!/bin/sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

HOSTS=$(echo $(basename $(dirname $(pwd))) | tr "_" "\n")

export $(xargs <${ROOT_DIR}/.env)

export VERNEMQ_SERVICE=${VERNEMQ_SERVICE_PROD}

${ROOT_DIR}/src/main/resources/config/mqtt.sh

printf "Entity Metadata publish script [supervisor] sleeping before publishing data topics ... " && sleep 2 && printf "done\n\nEntity Metadata publish script [supervisor] publishing data topics:\n"

for HOST in ${HOSTS}; do
  HOST="$(grep ${HOST} ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-${HOST}"
  printf "Entity Metadata publish script publishing data on [${HOST}]:\n"
  ssh -o StrictHostKeyChecking=no root@${HOST} "echo 'Run supervisor on [${HOST}]!'"
  printf "\n"
done
