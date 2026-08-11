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
    echo "       vernemq verify assert the broker retains exactly the declared topics"
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

printf '\nSchema verify [%s] against [%s]\n\n' "tasmota" "${VERNEMQ_SERVICE_PROD}"

COMMAND_TOPICS=("tasmota/device/ceiling_network_switch_plug/cmnd/POWER" "tasmota/device/ceiling_water_booster_plug/cmnd/POWER" "tasmota/device/deck_festoons_plug/cmnd/POWER" "tasmota/device/garden_pool_filter_plug/cmnd/POWER" "tasmota/device/kitchen_bench_lights_plug/cmnd/POWER" "tasmota/device/kitchen_fan_plug/cmnd/POWER" "tasmota/device/landing_festoons_plug/cmnd/POWER" "tasmota/device/rack_backup_plug/cmnd/POWER" "tasmota/device/rack_fans_plug/cmnd/POWER" "tasmota/device/rack_outlet_plug/cmnd/POWER" "tasmota/device/rack_printer_plug/cmnd/POWER" "tasmota/device/rack_screen_plug/cmnd/POWER")

FAULTS=0

while IFS= read -r TOPIC; do
  for COMMAND_TOPIC in ${COMMAND_TOPICS[@]+"${COMMAND_TOPICS[@]}"}; do
    [ "${TOPIC}" == "${COMMAND_TOPIC}" ] && continue 2
  done
  RETAINED="$(payload "${TOPIC}")"
  if [ -z "${RETAINED}" ]; then
    FAULTS=$((FAULTS + 1))
    printf 'declared topic has no retained payload [%s]\n' "${TOPIC}" >&2
  fi
done < <(declared)

RETAINED_FILE="$(mktemp)"
trap 'rm -f "${RETAINED_FILE}"' EXIT
topics "homeassistant/+/tasmota/#" >> "${RETAINED_FILE}"
topics "tasmota/#" >> "${RETAINED_FILE}"
while IFS= read -r TOPIC; do
  [ -z "${TOPIC}" ] && continue
  if ! declared | grep -qxF "${TOPIC}"; then
    FAULTS=$((FAULTS + 1))
    printf 'retained topic is stale, nothing declares it [%s]\n' "${TOPIC}" >&2
  fi
done < "${RETAINED_FILE}"

if [ "${FAULTS}" != "0" ]; then
  printf '\nSchema verify [%s] found [%s] fault(s)\n' "tasmota" "${FAULTS}" >&2
  exit 1
fi
printf '\nSchema verify [%s] found no drift\n' "tasmota"
