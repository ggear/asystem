#!/bin/bash

set -Eeuo pipefail

IFS=$'\n\t'

ROOT_DIR="$(dirname "$(readlink -f "$0")")"
HOSTS_FILE="${ROOT_DIR}/../../../.hosts"
SERVICE_NAME="$(basename "${ROOT_DIR}")"
SERVICE_LABEL="$(basename "$(dirname "${ROOT_DIR}")")"
INSTALL_DIR="/var/lib/asystem/install"
LINE="----------------------------------------------------------------------------------------------------"

MACHINE="$(grep "^${SERVICE_LABEL}=" "${HOSTS_FILE}" | cut -d'=' -f2 | cut -d',' -f1)"
HOST="${MACHINE}-${SERVICE_LABEL}"
INSTALL="${INSTALL_DIR}/${SERVICE_NAME}/latest/install.sh"

echo "${LINE}"
echo "Cycling service [${SERVICE_NAME}] on host [${HOST}] ... "
echo "${LINE}"
ssh -q "root@${HOST}.local" "[ -f '${INSTALL}' ] && chmod +x '${INSTALL}' && '${INSTALL}' start"
