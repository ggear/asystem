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
    echo "       vernemq config apply the declared device and group configuration to the bridge"
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

AWAITED_TIMEOUT=${AWAITED_TIMEOUT:-300}

awaited() {
  local started=${SECONDS} payload
  while true; do
    payload="$(mosquitto_sub "${BROKER_ARGS[@]}" -t "$1" -W 1 2>/dev/null)"
    if [ -n "${payload}" ] && jq -re "$2" <<<"${payload}" >/dev/null 2>&1; then
      return 0
    fi
    if [ $((SECONDS - started)) -ge "${AWAITED_TIMEOUT}" ]; then
      fail "Waited [$((SECONDS - started))] seconds for [$3] on topic [$1] against broker [${BROKER_SERVICE}]"         "The topic held no payload matching [$2], check the service is publishing and the broker is reachable"
      return 1
    fi
    printf 'Waiting for [%s] to come up ...\n' "$3"
    sleep 2
  done
}

printf '\nBroker config [%s] against [%s]\n\n' "zigbee2mqtt" "${BROKER_SERVICE}"

awaited "zigbee/bridge/state" '.state == "online"' "zigbee2mqtt" || exit 1

"${ROOT_DIR}/broker_config.py" '0x0017880103433075' 'Ada Lamp Bulb 1' 'Ada Lamp' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":254, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x001788010343c36f' 'Edwin Night Light Bulb 1' 'Edwin Night Light' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":3, "hue_power_on_color_temperature":454, "color_temp_startup":454 }'
"${ROOT_DIR}/broker_config.py" '0x00178801043283b0' 'Hallway Main Bulb 1' 'Hallway Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":3, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x0017880104329975' 'Hallway Main Bulb 2' 'Hallway Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":3, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x001788010432996f' 'Hallway Main Bulb 3' 'Hallway Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":3, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x001788010444db4e' 'Hallway Main Bulb 4' 'Hallway Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":3, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x2c1165fffe12d5c4' 'Hallway Sconces Bulb 1' 'Hallway Sconces' '{ "power_on_behavior":"on", "color_temp_startup":65279 }'
"${ROOT_DIR}/broker_config.py" '0x2c1165fffe109407' 'Hallway Sconces Bulb 2' 'Hallway Sconces' '{ "power_on_behavior":"on", "color_temp_startup":65279 }'
"${ROOT_DIR}/broker_config.py" '0x00178801039f69d5' 'Dining Main Bulb 1' 'Dining Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":254, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x00178801039f56c4' 'Dining Main Bulb 2' 'Dining Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":254, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x00178801039f584a' 'Dining Main Bulb 3' 'Dining Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":254, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x00178801039f69d4' 'Dining Main Bulb 4' 'Dining Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":254, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x00178801039f574e' 'Dining Main Bulb 5' 'Dining Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":254, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x00178801039f4eed' 'Dining Main Bulb 6' 'Dining Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":254, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x00178801039f6b78' 'Lounge Main Bulb 1' 'Lounge Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":254, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x001788010444ef85' 'Lounge Main Bulb 2' 'Lounge Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":254, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x00178801039f6b4a' 'Lounge Main Bulb 3' 'Lounge Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":254, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x001788010ec76d57' 'Lounge Lamp Bulb 1' 'Lounge Lamp' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":3, "hue_power_on_color_temperature":454, "color_temp_startup":454 }'
"${ROOT_DIR}/broker_config.py" '0x0017880106bc4f2d' 'Lounge Reading Bulb 1' 'Lounge Reading' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":3, "hue_power_on_color_temperature":454, "color_temp_startup":454 }'
"${ROOT_DIR}/broker_config.py" '0x00178801039f585a' 'Parents Main Bulb 1' 'Parents Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":3, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x00178801039f69d1' 'Parents Main Bulb 2' 'Parents Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":3, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x001788010432a064' 'Parents Main Bulb 3' 'Parents Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":3, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x2c1165fffeb07271' 'Parents Jane Bedside Bulb 1' 'Parents Jane Bedside' '{ "power_on_behavior":"on", "color_temp_startup":65279 }'
"${ROOT_DIR}/broker_config.py" '0x2c1165fffea8c4d8' 'Parents Graham Bedside Bulb 1' 'Parents Graham Bedside' '{ "power_on_behavior":"on", "color_temp_startup":65279 }'
"${ROOT_DIR}/broker_config.py" '0x00178801040e2034' 'Study Lamp Bulb 1' 'Study Lamp' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":254, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x00178801040f8db2' 'Kitchen Main Bulb 1' 'Kitchen Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":254, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x001788010343c34f' 'Kitchen Main Bulb 2' 'Kitchen Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":254, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x001788010343c147' 'Kitchen Main Bulb 3' 'Kitchen Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":254, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x001788010343b9d8' 'Kitchen Main Bulb 4' 'Kitchen Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":254, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x0017880104eaa288' 'Laundry Main Bulb 1' 'Laundry Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":254, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x0017880104eaa272' 'Pantry Main Bulb 1' 'Pantry Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":254, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x00178801040edfae' 'Office Main Bulb 1' 'Office Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":254, "hue_power_on_color_temperature":250, "color_temp_startup":250 }'
"${ROOT_DIR}/broker_config.py" '0x00178801040edcad' 'Bathroom Main Bulb 1' 'Bathroom Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":3, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x2c1165fffe2787f0' 'Bathroom Sconces Bulb 1' 'Bathroom Sconces' '{ "power_on_behavior":"on", "color_temp_startup":65279 }'
"${ROOT_DIR}/broker_config.py" '0x2c1165fffe18e424' 'Bathroom Sconces Bulb 2' 'Bathroom Sconces' '{ "power_on_behavior":"on", "color_temp_startup":65279 }'
"${ROOT_DIR}/broker_config.py" '0x00178801040eddb2' 'Ensuite Main Bulb 1' 'Ensuite Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":3, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
"${ROOT_DIR}/broker_config.py" '0x2c1165fffe168c7e' 'Ensuite Sconces Bulb 1' 'Ensuite Sconces' '{ "power_on_behavior":"on", "color_temp_startup":65279 }'
"${ROOT_DIR}/broker_config.py" '0x2c1165fffea5cd4b' 'Ensuite Sconces Bulb 2' 'Ensuite Sconces' '{ "power_on_behavior":"on", "color_temp_startup":65279 }'
"${ROOT_DIR}/broker_config.py" '0x2c1165fffea89f5f' 'Ensuite Sconces Bulb 3' 'Ensuite Sconces' '{ "power_on_behavior":"on", "color_temp_startup":65279 }'
"${ROOT_DIR}/broker_config.py" '0x00178801040ede93' 'Wardrobe Main Bulb 1' 'Wardrobe Main' '{ "hue_power_on_behavior":"on", "hue_power_on_brightness":254, "hue_power_on_color_temperature":65535, "color_temp_startup":65535 }'
