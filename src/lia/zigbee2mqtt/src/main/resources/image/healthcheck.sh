#!/bin/bash

set -eo pipefail

HEALTHCHECK_VERBOSE=${HEALTHCHECK_VERBOSE:-false}
if [ "${HEALTHCHECK_VERBOSE}" == true ]; then
  set -o xtrace
fi

function alive() {
  if [ "$(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_API_PORT} -t 'zigbee/bridge/state' -W 1 2>/dev/null)" == '{"state":"online"}' ]; then
    return 0
  else
    return 1
  fi
}

function ready() {
  if [ "$(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_API_PORT} -t 'zigbee/bridge/state' -W 1 2>/dev/null)" == '{"state":"online"}' ] &&
    [ $(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_API_PORT} -t 'zigbee/bridge/groups' -W 1 2>/dev/null | jq length 2>/dev/null) -gt 0 ] &&
    [ $(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_API_PORT} -t 'zigbee/bridge/devices' -W 1 2>/dev/null | jq length 2>/dev/null) -gt 0 ]; then
    return 0
  else
    return 1
  fi
}

[ "$#" -eq 1 ] && [ "${1}" == "alive" ] && exit $(alive)
exit $(ready)
