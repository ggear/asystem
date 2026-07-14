#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

export $(xargs <${ROOT_DIR}/.env) 2>/dev/null

HOME="/home/asystem/$(basename "${ROOT_DIR}")/latest"
INSTALL="/var/lib/asystem/install/$(basename "${ROOT_DIR}")/latest"
HOSTS=$(echo $(basename $(dirname ${ROOT_DIR})) | tr "_" "\n")

CSV_FILE="${ROOT_DIR}/src/build/resources/design/metadata/benchmark.csv"
REMOTE_BENCH="/root/install/storage/latest/benchmark.sh"

mkdir -p "$(dirname "${CSV_FILE}")"
[ -s "${CSV_FILE}" ] || printf '"Host","Mount","Date","Time","Read MB/s","Write MB/s"\n' >"${CSV_FILE}"

for LABEL in ${HOSTS}; do
  MACHINE="$(grep ${LABEL} ${ROOT_DIR}/../../../.hosts | tr '=' ' ' | tr ',' ' ' | awk '{ print $2 }')"
  [ "${MACHINE}" = "macmini" ] || continue
  HOST="${MACHINE}-${LABEL}"
  ssh -o StrictHostKeyChecking=no root@${HOST} \
    "[ -f ${REMOTE_BENCH} ] && ${REMOTE_BENCH} --csv" \
    | while IFS= read -r ROW; do
        printf '"%s",%s\n' "${LABEL}" "${ROW}" >>"${CSV_FILE}"
      done
  printf "\n"
done
