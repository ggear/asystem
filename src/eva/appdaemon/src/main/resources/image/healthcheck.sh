#!/bin/bash

POSITIONAL_ARGS=()
HEALTHCHECK_VERBOSE=${HEALTHCHECK_VERBOSE:-false}
while [[ $# -gt 0 ]]; do
  case $1 in
  -v | --verbose)
    HEALTHCHECK_VERBOSE=true
    shift
    ;;
  -h | --help | -*)
    echo "Usage: ${0} [-v|--verbose] [-h|--help] [alive]"
    exit 2
    ;;
  *)
    POSITIONAL_ARGS+=("$1")
    shift
    ;;
  esac
done
set -- "${POSITIONAL_ARGS[@]}"

if [ "${HEALTHCHECK_VERBOSE}" == true ]; then
  alias curl="curl -f --connect-timeout 2 --max-time 2"
  set -o xtrace
else
  alias curl="curl -sf --connect-timeout 2 --max-time 2"
fi

set -eo pipefail
shopt -s expand_aliases

function alive() {
  if
    [ "$(curl -LI "https://${APPDAEMON_SERVICE}:${APPDAEMON_HTTP_PORT}/aui/index.html" | tac | tac | head -n 1 | cut -d$' ' -f2)" == "200" ]
  then
    [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "Alive :)" >&2
    return 0
  else
    [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "Not Alive :(" >&2
    return 1
  fi
}

function ready() {
  if
    [ "$(curl -H "x-ad-access: ${APPDAEMON_TOKEN}" -H "Content-Type: application/json" "https://${APPDAEMON_SERVICE}:${APPDAEMON_HTTP_PORT}/api/appdaemon/health" | jq -er .health)" == "OK" ]
  then
    [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "Ready :)" >&2
    return 0
  else
    [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "Not Ready :(" >&2
    return 1
  fi
}

[ $# -eq 1 ] && [ "${1}" == "alive" ] && exit $(alive)
exit $(ready)
