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

BROKER_SERVICE="${BROKER_SERVICE:-${WEEWX_BROKER_SERVICE:-${VERNEMQ_SERVICE_PROD:-}}}"
BROKER_PORT="${BROKER_PORT:-${WEEWX_BROKER_PORT:-${VERNEMQ_API_PORT:-}}}"

for VARIABLE in BROKER_SERVICE BROKER_PORT; do
  if [ -z "${!VARIABLE}" ]; then
    echo "Schema script [weewx] could not resolve [${VARIABLE}] from it or any fallback, declare it in the module env files" >&2
    exit 1
  fi
done

BROKER_ARGS=(-h "$BROKER_SERVICE" -p "$BROKER_PORT")

if [ "${SCHEMA_PHASE}" != "publish" ]; then

printf '\nEntity Metadata publish script [weewx] dropping discovery topics on [%s]:\n' "$BROKER_SERVICE"
mosquitto_sub "${BROKER_ARGS[@]}" -F '%t' -t "homeassistant/+/weewx/#" -W 5 2>/dev/null | sort -u | \
  while read -r TOPIC; do
    printf '%s\n' "$TOPIC"
    mosquitto_pub "${BROKER_ARGS[@]}" -t "$TOPIC" -r -n
  done
mosquitto_sub "${BROKER_ARGS[@]}" --remove-retained -F '%t' -t "homeassistant/+/weewx/#" -W 5 2>/dev/null

printf '\nEntity Metadata publish script [weewx] sleeping before dropping data topics ... ' && sleep 2 && printf 'done\n\n'

printf 'Entity Metadata publish script [weewx] dropping data topics on [%s]:\n' "$BROKER_SERVICE"
mosquitto_sub "${BROKER_ARGS[@]}" --remove-retained -F '%t' -t "weewx/#" -W 1 2>/dev/null

printf '\nEntity Metadata publish script [weewx] sleeping before publishing discovery topics ... ' && sleep 2 && printf 'done\n\n'

fi

if [ "${SCHEMA_PHASE}" != "sweep" ]; then

printf 'Entity Metadata publish script [weewx] publishing discovery topics on [%s]:\n' "$BROKER_SERVICE"
find "$ROOT_DIR" -path "*/homeassistant/*/weewx/*/*" -name "*.json" -print0 | sort -z | while read -r -d $'\0' METADATA_FILE; do
  METADATA_TOPIC=$(dirname "${METADATA_FILE/$ROOT_DIR\//}")
  mosquitto_pub "${BROKER_ARGS[@]}" -t "$METADATA_TOPIC" -f "$METADATA_FILE" -r
  printf '%s\n' "$METADATA_TOPIC"
done
printf '\n'

fi
