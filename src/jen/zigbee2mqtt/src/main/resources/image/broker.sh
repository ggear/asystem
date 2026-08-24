#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

ROOT_DIR="$(dirname "$(readlink -f "$0")")/broker"

ENV_DIR="$ROOT_DIR"
while [ "$ENV_DIR" != "/" ] && [ ! -f "$ENV_DIR/.env" ]; do ENV_DIR="$(dirname "$ENV_DIR")"; done
# shellcheck disable=SC1091
[ -f "$ENV_DIR/.env" ] && . "$ENV_DIR/.env"

SCHEMA_PHASE="${1:-all}"
case "${SCHEMA_PHASE}" in
sweep | publish | all) ;;
*)
  echo "Usage: $(basename "$0") [sweep|publish]" >&2
  exit 2
  ;;
esac

BROKER_SERVICE="${BROKER_SERVICE:-${ZIGBEE2MQTT_BROKER_SERVICE:-${VERNEMQ_SERVICE_PROD:-}}}"
BROKER_PORT="${BROKER_PORT:-${ZIGBEE2MQTT_BROKER_PORT:-${VERNEMQ_API_PORT:-}}}"

for VARIABLE in BROKER_SERVICE BROKER_PORT; do
  if [ -z "${!VARIABLE}" ]; then
    echo "Schema script [zigbee2mqtt] could not resolve [${VARIABLE}] from it or any fallback, declare it in the module env files" >&2
    exit 1
  fi
done

BROKER_ARGS=(-h "$BROKER_SERVICE" -p "$BROKER_PORT")

printf 'Entity Metadata publish script [zigbee2mqtt] waiting for the service to republish its discovery topics ... ' && sleep 15 && printf 'done\n'

DISCOVERED=$(mosquitto_sub "${BROKER_ARGS[@]}" -F '%t' -t 'homeassistant/#' -W 5 2>/dev/null | grep -c '/0x' || true)
printf '\nEntity Metadata publish script [zigbee2mqtt] rediscovered [%s] devices\n\n' "${DISCOVERED}"
