#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")/broker"

ENV_DIR="$ROOT_DIR"
while [ "$ENV_DIR" != "/" ] && [ ! -f "$ENV_DIR/.env" ]; do ENV_DIR="$(dirname "$ENV_DIR")"; done
# shellcheck disable=SC1091
[ -f "$ENV_DIR/.env" ] && . "$ENV_DIR/.env"

for VARIABLE in VERNEMQ_SERVICE VERNEMQ_API_PORT; do
  if [ -z "${!VARIABLE:-}" ]; then
    echo "Entity Metadata publish script [zigbee2mqtt] could not resolve [${VARIABLE}] from [${ENV_DIR}/.env] or the environment" >&2
    exit 1
  fi
done

printf "\nEntity Metadata publish script [zigbee2mqtt] dropping discovery topics on [%s]:\n" "$VERNEMQ_SERVICE"
mosquitto_sub -h "$VERNEMQ_SERVICE" -p "$VERNEMQ_API_PORT" -F '%t' -t "homeassistant/#" -W 5 2>/dev/null | sort -u |
  while read -r topic; do
    base=$(basename "$(dirname "$(dirname "$topic")")")
    if [[ "$base" == 0x* ]] || [[ "$base" == 122* ]]; then
      echo "$topic"
      mosquitto_pub -h "$VERNEMQ_SERVICE" -p "$VERNEMQ_API_PORT" -t "$topic" -r -n
    fi
  done
mosquitto_sub -h "$VERNEMQ_SERVICE" -p "$VERNEMQ_API_PORT" -F '%t' -t "homeassistant/#" -W 5 2>/dev/null | sort -u |
  while read -r topic; do
    base=$(basename "$(dirname "$(dirname "$topic")")")
    if [[ "$base" == 0x* ]] || [[ "$base" == 122* ]]; then
      mosquitto_sub -h "$VERNEMQ_SERVICE" -p "$VERNEMQ_API_PORT" --remove-retained -F '%t' -t "$topic" -W 1 2>/dev/null
    fi
  done

printf "\nEntity Metadata publish script [zigbee2mqtt] sleeping before dropping data topics ... " && sleep 2 && printf "done\n\n"

printf "Entity Metadata publish script [zigbee2mqtt] dropping data topics on [%s]:\n" "$VERNEMQ_SERVICE"
mosquitto_sub -h "${VERNEMQ_SERVICE}" -p "${VERNEMQ_API_PORT}" --remove-retained -F '%t' -t 'zigbee/#' -W 1 2>/dev/null

printf "\nEntity Metadata publish script [zigbee2mqtt] sleeping before publishing discovery and data topics ... " && sleep 2 && printf "done\n\n"
