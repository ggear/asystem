#!/bin/bash

set -eo pipefail

HEALTHCHECK_VERBOSE=${HEALTHCHECK_VERBOSE:-false}
if [ "${HEALTHCHECK_VERBOSE}" == true ]; then
  set -o xtrace
fi

function alive() {
  if nc -z ${INFLUXDB3_SERVICE} ${INFLUXDB3_PORT}; then
    return 0
  else
    return 1
  fi
}

function ready() {
  if READY="$(influxdb3 show databases --format json)" &&
    [ "$(jq length <<<"${READY}")" -gt 0 ]; then
    return 0
  else
    return 1
  fi
}

[ "$#" -eq 1 ] && [ "${1}" == "alive" ] && exit $(alive)
exit $(ready)
