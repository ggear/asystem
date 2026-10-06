#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

SERVICE_HOME="/home/asystem/$(basename "${ROOT_DIR}")/latest"
HOST="$(grep "$(basename "$(dirname "${ROOT_DIR}")")" "${ROOT_DIR}/../../../.hosts" | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')"-"$(basename "$(dirname "${ROOT_DIR}")")"

rsync -av --delete "${ROOT_DIR}/src/main/resources/data/dashboards/" "root@${HOST}:${SERVICE_HOME}/dashboards/"
ssh "root@${HOST}" docker exec "$(basename "${ROOT_DIR}")" /asystem/etc/push.sh
