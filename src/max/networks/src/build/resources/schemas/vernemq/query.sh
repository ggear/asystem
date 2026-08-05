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
    echo "       vernemq query print the retained payload of every declared topic"
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
  echo "Schema script [networks] could not find env file [${MODULE_DIR}/.env]" >&2
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
  find "${ROOT_DIR}/topics" -type f -print0 2>/dev/null |
    while IFS= read -r -d '' LEAF; do
      printf '%s\n' "${LEAF#"${ROOT_DIR}"/topics/}"
    done | sort -u
}

printf '\nSchema query [%s] against [%s]\n\n' "networks" "${VERNEMQ_SERVICE_PROD}"
while IFS= read -r TOPIC; do
  printf '\n== %s ==\n' "${TOPIC}"
  payload "${TOPIC}"
done < <(declared)
