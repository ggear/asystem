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
  if ALIVE="$(${CURL_CMD} "http://${PLEX_SERVICE}:${PLEX_HTTP_PORT}/identity")" &&
    [ "$(xq -e '/MediaContainer/@version' <<<"${ALIVE}")" != "" ]; then
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "Alive :)") || return 0
  else
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "NOT Alive :(") || return 1
  fi
}

function ready() {
  if READY="$(${CURL_CMD} "http://${PLEX_SERVICE}:${PLEX_HTTP_PORT}/identity")" &&
    [ "$(xq -e '/MediaContainer/@claimed' <<<"${READY}")" == "1" ]; then
    for SHARE in /share/*; do
      if [ "$(ls -l $SHARE | grep -v '^total' | wc -l)" -eq 0 ]; then
        return 1
      fi
    done
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "Alive :)") || return 0
  else
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "NOT Alive :(") || return 1
  fi
}

[ "$#" -eq 1 ] && [ "${1}" == "alive" ] && exit $(alive)
exit $(ready)
