#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"
SHARES_FILE="${ROOT_DIR}/src/main/resources/shares.csv"
BIN_DIR="/var/lib/asystem/install/media/latest/bin"

COMMANDS_SINGLETON=("media-truncate" "media-refresh")
COMMANDS_ALL_HOSTS=("media-normalise" "media-clean" "media-analyse" "media-space")

RESULT=0
FAILURES=()

execute_remote() {
  local HOST=${1} && shift
  local COMMAND
  if ! host "${HOST}" >/dev/null 2>&1; then
    printf '\033[1;33m==> %s unreachable, skipping [%s]\033[0m\n' "${HOST}" "$*"
    FAILURES+=("${HOST} unreachable")
    RESULT=1
    return
  fi
  for COMMAND in "$@"; do
    printf '\033[1;36m==> %s %s\033[0m\n' "${HOST}" "${COMMAND}"
    if ! ssh -o StrictHostKeyChecking=no -t -t -q "root@${HOST}" "${BIN_DIR}/${COMMAND}.sh"; then
      printf '\033[1;31m==> %s %s failed\033[0m\n' "${HOST}" "${COMMAND}"
      FAILURES+=("${HOST} ${COMMAND}")
      RESULT=1
    fi
  done
}

[ -f "${SHARES_FILE}" ] || {
  echo "Missing shares file [${SHARES_FILE}]" >&2
  exit 1
}

HOSTS="$(cut -d "," -f 1 "${SHARES_FILE}" | sort -u)"
[ -n "${HOSTS}" ] || {
  echo "Missing shares hosts in file [${SHARES_FILE}]" >&2
  exit 1
}

execute_remote "$(echo "${HOSTS}" | head -1)" "${COMMANDS_SINGLETON[@]}"
for HOST in ${HOSTS}; do
  execute_remote "${HOST}" "${COMMANDS_ALL_HOSTS[@]}"
done

if [ ${RESULT} -ne 0 ]; then
  printf '\033[1;31m==> Deploy failed [%s]\033[0m\n' "${#FAILURES[@]}"
  printf '      %s\n' "${FAILURES[@]}"
fi

exit ${RESULT}
