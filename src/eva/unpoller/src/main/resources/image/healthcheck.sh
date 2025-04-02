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
  if [ "$(${CURL_CMD} "http://${UNPOLLER_SERVICE}:${UNPOLLER_HTTP_PORT}/health")" == "OK" ]; then
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "Alive :)") || return 0
  else
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "NOT Alive :(") || return 1
  fi
}

function ready() {
  if [ "$(${CURL_CMD} "http://${UNPOLLER_SERVICE}:${UNPOLLER_HTTP_PORT}/api/v1/output/influxdb/events" | jq -er .influxdb.latest | cut -d 'T' -f 1)" == "$(date --rfc-3339=ns | sed 's/ /T/' | cut -d 'T' -f 1)" ]; then
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "Alive :)") || return 0
  else
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "NOT Alive :(") || return 1
  fi
}

[ "$#" -eq 1 ] && [ "${1}" == "alive" ] && exit $(alive)
exit $(ready)
