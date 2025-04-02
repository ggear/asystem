#!/bin/bash

set -eo pipefail

HEALTHCHECK_VERBOSE=${HEALTHCHECK_VERBOSE:-false}
if [ "${HEALTHCHECK_VERBOSE}" == true ]; then
  set -o xtrace
fi

function alive() {
  if [ "$(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_API_PORT} -t 'zigbee/bridge/state' -W 1 2>/dev/null)" == '{"state":"online"}' ]; then
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "Alive :)") || return 0
  else
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "NOT Alive :(") || return 1
  fi
}
function ready() {

  #TODO: Improve to check correct number of groups/devices created

  if [ "$(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_API_PORT} -t 'zigbee/bridge/state' -W 1 2>/dev/null)" == '{"state":"online"}' ] &&
    [ $(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_API_PORT} -t 'zigbee/bridge/groups' -W 1 2>/dev/null | jq length 2>/dev/null) -gt 0 ] &&
    [ $(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_API_PORT} -t 'zigbee/bridge/devices' -W 1 2>/dev/null | jq length 2>/dev/null) -gt 0 ]; then
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "Alive :)") || return 0
  else
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "NOT Alive :(") || return 1
  fi

[ "$#" -eq 1 ] && [ "${1}" == "alive" ] && exit $(alive)
exit $(ready)
