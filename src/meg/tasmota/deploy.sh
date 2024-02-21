#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

export $(xargs <${ROOT_DIR}/.env)

export VERNEMQ_SERVICE=${VERNEMQ_SERVICE_PROD}

${ROOT_DIR}/src/main/resources/config/mqtt.sh
${ROOT_DIR}/src/build/resources/tasmota_config.sh
