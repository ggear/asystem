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
  if ALIVE="$(${CURL_CMD} "http://${APPDAEMON_SERVICE}:${APPDAEMON_HTTP_PORT}/health")" &&
    [ "${ALIVE}" == "OK" ]; then
    return 0
  else
    return 1
  fi
}

function ready() {
  #  TODO: Provide implementation that relfects on models being served
  if READY="$(${CURL_CMD} "http://${APPDAEMON_SERVICE}:${APPDAEMON_HTTP_PORT}/health")" &&
    [ "${READY}" == "OK" ]; then
    return 0
  else
    return 1
  fi
}

[ "$#" -eq 1 ] && [ "${1}" == "alive" ] && exit $(alive)
exit $(ready)
