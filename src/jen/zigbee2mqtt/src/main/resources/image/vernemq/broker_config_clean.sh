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
    echo "       vernemq clean remove every declared device from all of its bridge groups"
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

if [ -f "${MODULE_DIR}/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "${MODULE_DIR}/.env"
  set +a
fi

if [ "${SCHEMA_VERBOSE}" == true ]; then
  set -x
fi

BROKER_SERVICE="${BROKER_SERVICE:-${ZIGBEE2MQTT_BROKER_SERVICE:-${VERNEMQ_SERVICE:-${VERNEMQ_SERVICE_PROD:-}}}}"
BROKER_PORT="${BROKER_PORT:-${ZIGBEE2MQTT_BROKER_PORT:-${VERNEMQ_API_PORT:-}}}"

for VARIABLE in BROKER_SERVICE BROKER_PORT; do
  if [ -z "${!VARIABLE}" ]; then
    echo "Schema script [zigbee2mqtt] could not resolve [${VARIABLE}] from it or any fallback, declare it in the module env files" >&2
    exit 1
  fi
done

fail() {
  printf '\n%s\n%s\n%s\n\n%s\n\n%s\n\n' \
    "################################################################################" \
    "SCHEMA FAILURE" \
    "################################################################################" \
    "$1" "$2" >&2
}

BROKER_ARGS=(-h "${BROKER_SERVICE}" -p "${BROKER_PORT}")

awaited() {
  while ! mosquitto_sub "${BROKER_ARGS[@]}" -t "$1" -W 1 2>/dev/null | jq -re "$2" >/dev/null; do
    printf 'Waiting for [%s] to come up ...\n' "$3"
    sleep 2
  done
}

printf '\nBroker clean [%s] against [%s]\n\n' "zigbee2mqtt" "${BROKER_SERVICE}"

awaited "zigbee/bridge/health" '.process.uptime_sec > 0' "zigbee2mqtt"

mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Ada Lamp Bulb 1" }' &&
  printf 'Device [%s] removed from all groups\n' 'Ada Lamp Bulb 1' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Edwin Night Light Bulb 1" }' &&
  printf 'Device [%s] removed from all groups\n' 'Edwin Night Light Bulb 1' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Hallway Main Bulb 1" }' &&
  printf 'Device [%s] removed from all groups\n' 'Hallway Main Bulb 1' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Hallway Main Bulb 2" }' &&
  printf 'Device [%s] removed from all groups\n' 'Hallway Main Bulb 2' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Hallway Main Bulb 3" }' &&
  printf 'Device [%s] removed from all groups\n' 'Hallway Main Bulb 3' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Hallway Main Bulb 4" }' &&
  printf 'Device [%s] removed from all groups\n' 'Hallway Main Bulb 4' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Hallway Sconces Bulb 1" }' &&
  printf 'Device [%s] removed from all groups\n' 'Hallway Sconces Bulb 1' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Hallway Sconces Bulb 2" }' &&
  printf 'Device [%s] removed from all groups\n' 'Hallway Sconces Bulb 2' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Dining Main Bulb 1" }' &&
  printf 'Device [%s] removed from all groups\n' 'Dining Main Bulb 1' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Dining Main Bulb 2" }' &&
  printf 'Device [%s] removed from all groups\n' 'Dining Main Bulb 2' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Dining Main Bulb 3" }' &&
  printf 'Device [%s] removed from all groups\n' 'Dining Main Bulb 3' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Dining Main Bulb 4" }' &&
  printf 'Device [%s] removed from all groups\n' 'Dining Main Bulb 4' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Dining Main Bulb 5" }' &&
  printf 'Device [%s] removed from all groups\n' 'Dining Main Bulb 5' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Dining Main Bulb 6" }' &&
  printf 'Device [%s] removed from all groups\n' 'Dining Main Bulb 6' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Lounge Main Bulb 1" }' &&
  printf 'Device [%s] removed from all groups\n' 'Lounge Main Bulb 1' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Lounge Main Bulb 2" }' &&
  printf 'Device [%s] removed from all groups\n' 'Lounge Main Bulb 2' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Lounge Main Bulb 3" }' &&
  printf 'Device [%s] removed from all groups\n' 'Lounge Main Bulb 3' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Lounge Lamp Bulb 1" }' &&
  printf 'Device [%s] removed from all groups\n' 'Lounge Lamp Bulb 1' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Lounge Reading Bulb 1" }' &&
  printf 'Device [%s] removed from all groups\n' 'Lounge Reading Bulb 1' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Parents Main Bulb 1" }' &&
  printf 'Device [%s] removed from all groups\n' 'Parents Main Bulb 1' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Parents Main Bulb 2" }' &&
  printf 'Device [%s] removed from all groups\n' 'Parents Main Bulb 2' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Parents Main Bulb 3" }' &&
  printf 'Device [%s] removed from all groups\n' 'Parents Main Bulb 3' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Parents Jane Bedside Bulb 1" }' &&
  printf 'Device [%s] removed from all groups\n' 'Parents Jane Bedside Bulb 1' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Parents Graham Bedside Bulb 1" }' &&
  printf 'Device [%s] removed from all groups\n' 'Parents Graham Bedside Bulb 1' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Study Lamp Bulb 1" }' &&
  printf 'Device [%s] removed from all groups\n' 'Study Lamp Bulb 1' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Kitchen Main Bulb 1" }' &&
  printf 'Device [%s] removed from all groups\n' 'Kitchen Main Bulb 1' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Kitchen Main Bulb 2" }' &&
  printf 'Device [%s] removed from all groups\n' 'Kitchen Main Bulb 2' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Kitchen Main Bulb 3" }' &&
  printf 'Device [%s] removed from all groups\n' 'Kitchen Main Bulb 3' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Kitchen Main Bulb 4" }' &&
  printf 'Device [%s] removed from all groups\n' 'Kitchen Main Bulb 4' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Laundry Main Bulb 1" }' &&
  printf 'Device [%s] removed from all groups\n' 'Laundry Main Bulb 1' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Pantry Main Bulb 1" }' &&
  printf 'Device [%s] removed from all groups\n' 'Pantry Main Bulb 1' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Office Main Bulb 1" }' &&
  printf 'Device [%s] removed from all groups\n' 'Office Main Bulb 1' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Bathroom Main Bulb 1" }' &&
  printf 'Device [%s] removed from all groups\n' 'Bathroom Main Bulb 1' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Bathroom Sconces Bulb 1" }' &&
  printf 'Device [%s] removed from all groups\n' 'Bathroom Sconces Bulb 1' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Bathroom Sconces Bulb 2" }' &&
  printf 'Device [%s] removed from all groups\n' 'Bathroom Sconces Bulb 2' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Ensuite Main Bulb 1" }' &&
  printf 'Device [%s] removed from all groups\n' 'Ensuite Main Bulb 1' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Ensuite Sconces Bulb 1" }' &&
  printf 'Device [%s] removed from all groups\n' 'Ensuite Sconces Bulb 1' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Ensuite Sconces Bulb 2" }' &&
  printf 'Device [%s] removed from all groups\n' 'Ensuite Sconces Bulb 2' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Ensuite Sconces Bulb 3" }' &&
  printf 'Device [%s] removed from all groups\n' 'Ensuite Sconces Bulb 3' && sleep 1
mosquitto_pub "${BROKER_ARGS[@]}" -t 'zigbee/bridge/request/group/members/remove_all' -m '{ "device": "Wardrobe Main Bulb 1" }' &&
  printf 'Device [%s] removed from all groups\n' 'Wardrobe Main Bulb 1' && sleep 1
