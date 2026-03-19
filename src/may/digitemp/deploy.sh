#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"
HOST="$(grep "$(basename "$(dirname "${ROOT_DIR}")")" "${ROOT_DIR}/../../../.hosts" | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')"-"$(basename "$(dirname "${ROOT_DIR}")")"

ssh -o StrictHostKeyChecking=no root@${HOST} "/root/install/zigbee2mqtt/latest/install.sh"
ssh -o StrictHostKeyChecking=no root@${HOST} "docker exec digitemp telegraf --debug --once"
