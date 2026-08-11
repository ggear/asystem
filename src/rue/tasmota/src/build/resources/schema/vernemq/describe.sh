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
MODULE_DIR="${ROOT_DIR}"
while [ "${MODULE_DIR}" != "/" ] && [ ! -f "${MODULE_DIR}/.env" ]; do
  MODULE_DIR="$(dirname "${MODULE_DIR}")"
done

if [ ! -f "${MODULE_DIR}/.env" ]; then
  echo "Schema script [tasmota] could not find env file [.env] searching up from [${ROOT_DIR}]" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
. "${MODULE_DIR}/.env"
set +a

if [ "${SCHEMA_VERBOSE}" == true ]; then
  set -x
fi

fail() {
  printf '\n%s\n%s\n%s\n\n%s\n\n%s\n\n' \
    "################################################################################" \
    "SCHEMA FAILURE" \
    "################################################################################" \
    "$1" "$2" >&2
}

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

printf '\nSchema describe [%s] against [%s]\n\n' "tasmota" "${VERNEMQ_SERVICE_PROD}"
printf '\n== %s ==\n' "homeassistant/+/tasmota/#"
topics "homeassistant/+/tasmota/#"
printf '\n== %s ==\n' "tasmota/#"
topics "tasmota/#"
