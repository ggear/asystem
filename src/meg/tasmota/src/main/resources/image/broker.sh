#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

ROOT_DIR="$(dirname "$(readlink -f "$0")")/broker"

ENV_DIR="$ROOT_DIR"
while [ "$ENV_DIR" != "/" ] && [ ! -f "$ENV_DIR/.env" ]; do ENV_DIR="$(dirname "$ENV_DIR")"; done
# shellcheck disable=SC1091
[ -f "$ENV_DIR/.env" ] && . "$ENV_DIR/.env"

BROKER_SERVICE="${BROKER_SERVICE:-${TASMOTA_BROKER_SERVICE:-${VERNEMQ_SERVICE_PROD:-}}}"
BROKER_PORT="${BROKER_PORT:-${TASMOTA_BROKER_PORT:-${VERNEMQ_API_PORT:-}}}"

for VARIABLE in BROKER_SERVICE BROKER_PORT; do
  if [ -z "${!VARIABLE}" ]; then
    echo "Schema script [tasmota] could not resolve [${VARIABLE}] from it or any fallback, declare it in the module env files" >&2
    exit 1
  fi
done

BROKER_ARGS=(-h "$BROKER_SERVICE" -p "$BROKER_PORT")

printf '\nEntity Metadata publish script [tasmota] dropping discovery topics on [%s]:\n' "$BROKER_SERVICE"
mosquitto_sub "${BROKER_ARGS[@]}" -F '%t' -t "homeassistant/+/tasmota/#" -W 5 2>/dev/null | sort -u | \
  while read -r TOPIC; do
    printf '%s\n' "$TOPIC"
    mosquitto_pub "${BROKER_ARGS[@]}" -t "$TOPIC" -r -n
  done
mosquitto_sub "${BROKER_ARGS[@]}" --remove-retained -F '%t' -t "homeassistant/+/tasmota/#" -W 5 2>/dev/null

printf '\nEntity Metadata publish script [tasmota] sleeping before dropping data topics ... ' && sleep 2 && printf 'done\n\n'

printf 'Entity Metadata publish script [tasmota] dropping data topics on [%s]:\n' "$BROKER_SERVICE"
mosquitto_sub "${BROKER_ARGS[@]}" --remove-retained -F '%t' -t "tasmota/device/#" -W 1 2>/dev/null

printf '\nEntity Metadata publish script [tasmota] sleeping before publishing discovery topics ... ' && sleep 2 && printf 'done\n\n'

printf 'Entity Metadata publish script [tasmota] publishing discovery topics on [%s]:\n' "$BROKER_SERVICE"
find "$ROOT_DIR" -path "*/homeassistant/*/tasmota/*/*" -name "*.json" -print0 | sort -z | while read -r -d $'\0' METADATA_FILE; do
  METADATA_TOPIC=$(dirname "${METADATA_FILE/$ROOT_DIR\//}")
  mosquitto_pub "${BROKER_ARGS[@]}" -t "$METADATA_TOPIC" -f "$METADATA_FILE" -r
  printf '%s\n' "$METADATA_TOPIC"
done
printf '\n'

printf 'Entity Metadata publish script [tasmota] restarting devices to republish their retained state:\n'
DEVICES=()
while IFS= read -r DEVICE; do
  DEVICES+=("${DEVICE}")
done < <(find "$ROOT_DIR" -name "*.json" -exec grep -ho '"availability_topic": *"[^"]*"' {} + |
  cut -d'"' -f4 | cut -d/ -f3 | sort -u)
for DEVICE in "${DEVICES[@]}"; do
  printf '%s\n' "${DEVICE}"
  mosquitto_pub "${BROKER_ARGS[@]}" -t "tasmota/device/${DEVICE}/cmnd/Restart" -m "1"
done

printf '\nEntity Metadata publish script [tasmota] waiting for devices to boot ... ' && sleep 30 && printf 'done\n'

RESTARTED=$(mosquitto_sub "${BROKER_ARGS[@]}" -F '%t' -t 'tasmota/device/+/tele/LWT' -W 5 2>/dev/null | sort -u | wc -l | tr -d ' ')
printf '\nEntity Metadata publish script [tasmota] restarted [%s] of [%d] devices\n\n' "${RESTARTED}" "${#DEVICES[@]}"
