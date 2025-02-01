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
  if ALIVE="$(${CURL_CMD} -LI "http://${APPDAEMON_SERVICE}:${APPDAEMON_HTTP_PORT}/aui/index.html" | head -n 1 | cut -d$' ' -f2)" &&
    [ "${ALIVE}" == "200" ]; then
    return 0
  else
    return 1
  fi
}

function ready() {

#  curl -i -X POST -H "x-ad-access: ${APPDAEMON_API_TOKEN}" -H "Content-Type: application/json" "http://${APPDAEMON_SERVICE}:${APPDAEMON_HTTP_API_PORT}/api/appdaemon/hello" -d '{"type": "Hello World Test"}'
#  curl -i -X POST -H "x-ad-access: ${APPDAEMON_TOKEN}" -H "Content-Type: application/json" "http://${APPDAEMON_SERVICE}:${APPDAEMON_HTTP_PORT}/api/appdaemon/hello" -d '{"type": "Hello World Test"}'

  if [ alive == "0" ]; then
    return 0
  else
    return 1
  fi
}

[ "$#" -eq 1 ] && [ "${1}" == "alive" ] && exit $(alive)
exit $(ready)
