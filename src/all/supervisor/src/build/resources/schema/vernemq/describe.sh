#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

set -uo pipefail

SCHEMA_VERBOSE=${SCHEMA_VERBOSE:-false}
while [[ $# -gt 0 ]]; do
  case $1 in
  -v | --verbose)
    SCHEMA_VERBOSE=true
    shift
    ;;
  -h | --help | -*)
    echo "Usage: ${0} [-v|--verbose] [-h|--help]"
    echo "       vernemq describe print what the production broker actually retains"
    exit 2
    ;;
  *)
    shift
    ;;
  esac
done

ROOT_DIR="$(dirname "$(readlink -f "$0")")"
MODULE_DIR="$(readlink -f "${ROOT_DIR}/../../../../..")"

if [ ! -f "${MODULE_DIR}/.env" ]; then
  echo "Schema script [supervisor] could not find env file [${MODULE_DIR}/.env]" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
. "${MODULE_DIR}/.env"
set +a

if [ "${SCHEMA_VERBOSE}" == true ]; then
  set -x
fi

BROKER_ARGS=(-h "${VERNEMQ_SERVICE_PROD}" -p "${VERNEMQ_API_PORT}")

topics() {
  mosquitto_sub "${BROKER_ARGS[@]}" -F '%t' -t "$1" -W 5 2>/dev/null | grep -E "${2:-.}" | sort -u
}

payload() {
  mosquitto_sub "${BROKER_ARGS[@]}" -t "$1" -C 1 -W 2 2>/dev/null
}

declared() {
  find "${ROOT_DIR}/model" -type f -print0 2>/dev/null |
    while IFS= read -r -d '' LEAF; do
      printf '%s\n' "${LEAF#"${ROOT_DIR}"/model/}"
    done | sort -u
}

printf '\nSchema describe [%s] against [%s]\n\n' "supervisor" "${VERNEMQ_SERVICE_PROD}"
printf '\n== %s ==\n' "homeassistant/+/+/+/config"
topics "homeassistant/+/+/+/config" "^homeassistant/[^/]+/supervisor_[^/]+/[^/]+/config$"
printf '\n== %s ==\n' "supervisor/+/data/#"
topics "supervisor/+/data/#"
