#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

export $(xargs <${ROOT_DIR}/.env) 2>/dev/null

HOME="/home/asystem/$(basename "${ROOT_DIR}")/latest"
INSTALL="/var/lib/asystem/install/$(basename "${ROOT_DIR}")/latest"
HOSTS=$(echo $(basename $(dirname $(pwd))) | tr "_" "\n")

for HOST in ${HOSTS}; do
  HOST="$(grep ${HOST} ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')-${HOST}"
  ssh -o StrictHostKeyChecking=no root@${HOST} "[ -f /root/install/supervisor/latest/install.sh ] && /root/install/supervisor/latest/install.sh"
  printf "\n"
done
