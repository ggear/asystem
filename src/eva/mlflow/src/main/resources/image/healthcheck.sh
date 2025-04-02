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
  if ALIVE="$(${CURL_CMD} "http://${MLFLOW_SERVICE}:${MLFLOW_HTTP_PORT}/health")" &&
    [ "${ALIVE}" == "OK" ]; then
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "Alive :)") || return 0
  else
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "NOT Alive :(") || return 1
  fi
}
function ready() {
  #  TODO: Provide implementation that reflects on models being served
  if READY="$(${CURL_CMD} "http://${MLFLOW_SERVICE}:${MLFLOW_HTTP_PORT}/health")" &&
    [ "${READY}" == "OK" ]; then
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "Alive :)") || return 0
  else
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "NOT Alive :(") || return 1
  fi

[ "$#" -eq 1 ] && [ "${1}" == "alive" ] && exit $(alive)
exit $(ready)
