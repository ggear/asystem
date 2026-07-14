#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

export $(xargs <${ROOT_DIR}/.env) 2>/dev/null

HOSTS=$(echo "${STORAGE_HOST_PROD}" | tr ',' ' ')

CSV_FILE="${ROOT_DIR}/src/build/resources/design/metadata/benchmark.csv"
REMOTE_BENCH="/root/install/storage/latest/benchmark.sh"

mkdir -p "$(dirname "${CSV_FILE}")"
[ -s "${CSV_FILE}" ] || printf '"Host","Mount","Used %%","Date","Time","Read MB/s","Write MB/s"\n' >"${CSV_FILE}"

cleanup_remote() {
  [ -n "${HOST:-}" ] && ssh -o StrictHostKeyChecking=no root@${HOST}.local \
    'pkill -TERM -f benchmark.sh; pkill -TERM fio' 2>/dev/null
  exit 130
}
trap cleanup_remote INT

for HOST in ${HOSTS}; do
  case "${HOST}" in
  macmini-*) ;;
  *) continue ;;
  esac
  LABEL="${HOST#*-}"
  printf '\033[1;36m==> Benchmarking %s\033[0m\n' "${HOST}"
  ssh -o StrictHostKeyChecking=no root@${HOST}.local \
    "[ -f ${REMOTE_BENCH} ] && ${REMOTE_BENCH} --csv" \
    | while IFS= read -r ROW; do
        printf '"%s",%s\n' "${LABEL}" "${ROW}" >>"${CSV_FILE}"
      done
  printf "\n"
done
