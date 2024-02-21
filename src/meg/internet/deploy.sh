#!/bin/sh

ROOT_DIR=$(dirname $(readlink -f "$0"))

HOST="$(grep $(basename $(dirname ${ROOT_DIR})) ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-$(basename $(dirname ${ROOT_DIR}))"

export $(xargs <${ROOT_DIR}/.env)

export VERNEMQ_SERVICE=${VERNEMQ_SERVICE_PROD}

${ROOT_DIR}/src/main/resources/config/mqtt.sh

printf "Entity Metadata publish script [internet] sleeping before publishing data topics ... " && sleep 2 && printf "done\n\nEntity Metadata publish script [internet] publishing data topics:\n"

ssh root@${HOST} "docker exec internet telegraf --debug --once"
