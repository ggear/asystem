#!/bin/bash

set -eo pipefail

HEALTHCHECK_VERBOSE=${HEALTHCHECK_VERBOSE:-false}
if [ "${HEALTHCHECK_VERBOSE}" == true ]; then
  set -o xtrace
fi

function alive() {
  if netcat -zw 1 ${RHASSPY_SERVICE} ${RHASSPY_API_PORT}; then
    return 0
  else
    return 1
  fi
}

function ready() {
  if [ "$(jq -er .model_version /train/en_US-rhasspy/training_info.json)" == "1.0" ]; then
    return 0
  else
    return 1
  fi
}

[ "$#" -eq 1 ] && [ "${1}" == "alive" ] && exit $(alive)
exit $(ready)
