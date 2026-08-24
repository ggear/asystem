#!/bin/bash

set -Eeuo pipefail

IFS=$'\n\t'

ROOT_DIR="$(dirname "$(readlink -f "$0")")"
LINE="----------------------------------------------------------------------------------------------------"
FAILED=0

if [[ -f "${ROOT_DIR}/.env" ]]; then
  # shellcheck disable=SC1091
  . "${ROOT_DIR}/.env"
fi

export BROKER_SERVICE="${BROKER_SERVICE:-127.0.0.1}"
export BROKER_PORT="${BROKER_PORT:-${VERNEMQ_API_PORT:-}}"

if [[ -z "${BROKER_PORT}" ]]; then
  echo "ERROR: Broker scripts skipped, could not resolve [BROKER_PORT] from [${ROOT_DIR}/.env]" >&2
  exit 1
fi

echo "Executing broker scripts against the local broker [${BROKER_SERVICE}] port [${BROKER_PORT}]"

while IFS= read -r BROKER_SCRIPT; do
  MODULE_NAME="$(basename "${BROKER_SCRIPT%%/src/main/*}")"
  echo ""
  echo "${LINE}"
  echo "Executing broker script for module [${MODULE_NAME}] starting ... "
  echo "${LINE}"
  echo ""
  if ! "${BROKER_SCRIPT}"; then
    FAILED=$((FAILED + 1))
    echo "WARN: Broker script failed for module [${MODULE_NAME}]" >&2
  fi
  echo ""
  echo "${LINE}"
  echo "Executing broker script for module [${MODULE_NAME}] finished"
  echo "${LINE}"
  echo ""
done < <(find "${ROOT_DIR}/../.." -name broker.sh -type f -path "*/src/main/*" ! -path "*/target/*" | sort)

if [[ "${FAILED}" -gt 0 ]]; then
  echo "ERROR: Broker scripts failed for [${FAILED}] modules" >&2
  exit 1
fi
