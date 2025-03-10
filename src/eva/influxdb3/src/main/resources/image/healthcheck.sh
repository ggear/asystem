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
  if ${CURL_CMD} "http://${INFLUXDB3_SERVICE}:${INFLUXDB3_PORT}/api/v3/configure/database?format=csv&show_deleted=false" >/dev/null 2>&1; then
    return 0
  else
    return 1
  fi
}

function ready() {
  if READY="$(${CURL_CMD} "http://${INFLUXDB3_SERVICE}:${INFLUXDB3_PORT}/api/v3/configure/database?format=csv&show_deleted=false")" &&
    [ "$(grep -c host_private <<<"${READY}")" -eq 1 ]; then
    echo return 0
  else
    echo return 1
  fi
}

[ "$#" -eq 1 ] && [ "${1}" == "alive" ] && exit $(alive)
exit $(ready)
