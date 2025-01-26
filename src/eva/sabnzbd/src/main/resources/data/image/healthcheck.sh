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
  if PID="$(${CURL_CMD} "http://${SABNZBD_SERVICE_PROD}:${SABNZBD_HTTP_PORT}/sabnzbd/api?output=json&apikey=${SABNZBD_API_KEY}&mode=status&skip_dashboard=0")" &&
    [ "$(jq -er '.pid' <<<"${PID}")" -gt 0 ]; then
    return 0
  else
    return 1
  fi
}

function ready() {
  if STATUS="$(${CURL_CMD} "http://${SABNZBD_SERVICE_PROD}:${SABNZBD_HTTP_PORT}/sabnzbd/api?output=json&apikey=${SABNZBD_API_KEY}&mode=status&skip_dashboard=0")" &&
    [ "$(jq -er '.status.paused' <<<"${STATUS}")" == "false" ] &&
    [ "$(jq -er '[.status.servers[].servertotalconn] | add' <<<"${STATUS}")" -gt 0 ]; then
    return 0
  else
    return 1
  fi
}

[ "$#" -eq 1 ] && [ "${1}" == "alive" ] && exit $(alive)
exit $(ready)
