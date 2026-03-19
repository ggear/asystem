#!/bin/sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

export $(xargs <${ROOT_DIR}/.env) 2>/dev/null

HOME="/home/asystem/$(basename "${ROOT_DIR}")/latest"
INSTALL="/var/lib/asystem/install/$(basename "${ROOT_DIR}")/latest"
HOST="$(grep "$(basename "$(dirname "${ROOT_DIR}")")" "${ROOT_DIR}/../../../.hosts" | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')"-"$(basename "$(dirname "${ROOT_DIR}")")"
export VERNEMQ_SERVICE=${VERNEMQ_SERVICE_PROD}

${ROOT_DIR}/src/main/resources/image/mqtt/mqtt_config.sh
ssh -o StrictHostKeyChecking=no root@${HOST} "/root/install/zigbee2mqtt/latest/install.sh"
