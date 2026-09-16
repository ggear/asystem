#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"
SHARES_FILE="${ROOT_DIR}/src/main/resources/shares.csv"
BIN_DIR="/var/lib/asystem/install/media/latest/bin"

COMMANDS_SINGLETON=("truncate" "refresh")
COMMANDS_ALL_HOSTS=("normalise" "clean" "analyse")

RESULT=0
FAILURES=()

execute_remote() {
  local HOST=${1} && shift
  local COMMAND
  if ! host "${HOST}" >/dev/null 2>&1; then
    printf '\033[1;33m%s unreachable, skipping [%s]\033[0m\n' "${HOST}" "$*"
    FAILURES+=("${HOST} unreachable")
    RESULT=1
    return
  fi
  for COMMAND in "$@"; do
    if ! ssh -o StrictHostKeyChecking=no -t -t -q "root@${HOST}" "MEDIA_REMOTE=1" "MEDIA_NESTED=1" "${BIN_DIR}/media.sh" "${COMMAND}"; then
      printf '\033[1;31mdeploy [%s] failed on [%s]\033[0m\n' "${COMMAND}" "${HOST}"
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
  printf '\n\033[1;31m== deploy failed [%s] ==\033[0m\n\n' "${#FAILURES[@]}"
  printf '      %s\n' "${FAILURES[@]}"
fi

exit ${RESULT}
