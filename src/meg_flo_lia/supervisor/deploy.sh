#!/bin/sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

HOSTS=$(echo $(basename $(dirname $(pwd))) | tr "_" "\n")

export $(xargs <${ROOT_DIR}/.env)

export VERNEMQ_HOST=${VERNEMQ_HOST_PROD}

${ROOT_DIR}/src/main/resources/config/mqtt.sh

printf "Entity Metadata publish script sleeping before publishing data ... " && sleep 2 && printf "done\n\nEntity Metadata publish script publishing data:\n"
for HOST in ${HOSTS}; do
  HOST="$(grep ${HOST} ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-${HOST}"
  ssh -o StrictHostKeyChecking=no root@${HOST} "echo 'Run supervisor on [${HOST}]!'"
done


