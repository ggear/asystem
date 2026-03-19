#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

HOST="$(grep "$(basename "$(dirname "${ROOT_DIR}")")" "${ROOT_DIR}/../../../.hosts" | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')"-"$(basename "$(dirname "${ROOT_DIR}")")"

ssh root@${HOST} "docker exec weectl report run --date=$(date +%Y-%m-%d) --after=$(date -d '15 minutes ago' +%Y-%m-%dT%H:%M)"
ssh root@${HOST} "docker exec weectl report run --date=$(date +%Y-%m-%d) --after=$(date -d '15 minutes ago' +%Y-%m-%dT%H:%M)"
