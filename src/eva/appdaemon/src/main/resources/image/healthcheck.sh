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
  if ALIVE="$(${CURL_CMD} -LI "https://${APPDAEMON_SERVICE}:${APPDAEMON_HTTP_PORT}/aui/index.html" | tac | tac | head -n 1 | cut -d$' ' -f2)" &&
    [ "${ALIVE}" == "200" ]; then
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "Alive :)") || return 0
  else
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "NOT Alive :(") || return 1
  fi
}

function ready() {
  if READY="$(${CURL_CMD} -H "x-ad-access: ${APPDAEMON_TOKEN}" -H "Content-Type: application/json" "https://${APPDAEMON_SERVICE}:${APPDAEMON_HTTP_PORT}/api/appdaemon/health")" &&
    [ "$(jq -er .health <<<"${READY}")" == "OK" ]; then
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "Alive :)") || return 0
  else
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "NOT Alive :(") || return 1
  fi
}

[ "$#" -eq 1 ] && [ "${1}" == "alive" ] && exit $(alive)
exit $(ready)
