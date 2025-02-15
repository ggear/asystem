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
  if [ $(${CURL_CMD} "http://127.0.0.1:8181/api/v3/configure/database?format=pretty&show_deleted=false" 2>/dev/null | wc) -gt 0 ]; then
    return 0
  else
    return 1
  fi
}

function ready() {
  if READY="$(influxdb3 show databases --format json)" &&
    [ "$(grep -c host_private <<<"${READY}")" -eq 1 ]; then
    return 0
  else
    return 1
  fi
}

[ "$#" -eq 1 ] && [ "${1}" == "alive" ] && exit $(alive)
exit $(ready)
