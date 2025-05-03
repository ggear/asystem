#!/bin/bash

set -eo pipefail

HEALTHCHECK_VERBOSE=${HEALTHCHECK_VERBOSE:-false}
if [ "${HEALTHCHECK_VERBOSE}" == true ]; then
  CURL_CMD="curl -f --connect-timeout 2 --max-time 2"
  set -o xtrace
else
  CURL_CMD="curl -sf --connect-timeout 2 --max-time 2"
fi

function alive() {
  if ALIVE="$(curl -H "Authorization: Bearer ${HOMEASSISTANT_API_TOKEN}" "http://${HOMEASSISTANT_SERVICE}:${HOMEASSISTANT_HTTP_PORT}/api/" | jq -er .message <<<"${ALIVE}")" == "API running." ]; then
    return 0
  else
    return 1
  fi
}

function ready() {
  if READY="$(curl -H "Authorization: Bearer ${HOMEASSISTANT_API_TOKEN}" -H "Content-Type: application/json" "http://${HOMEASSISTANT_SERVICE}:${HOMEASSISTANT_HTTP_PORT}/api/states/input_boolean.home_started" | jq -er .state)" == "on" ]; then
    return 0
  else
    return 1
  fi
}

[ "$#" -eq 1 ] && [ "${1}" == "alive" ] && exit $(alive)
exit $(ready)
