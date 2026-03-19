#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"
HOST="$(grep "$(basename "$(dirname "${ROOT_DIR}")")" "${ROOT_DIR}/../../../.hosts" | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')"-"$(basename "$(dirname "${ROOT_DIR}")")"

ssh -o StrictHostKeyChecking=no root@${HOST} "/root/install/vernemq/latest/install.sh"
${ROOT_DIR}/install_local.sh
