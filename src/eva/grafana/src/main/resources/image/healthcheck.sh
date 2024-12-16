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
  if ALIVE="$(${CURL_CMD} "${GRAFANA_URL}/api/health" | jq -er .database | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')" &&
    [ "${ALIVE}" == "ok" ]; then
    return 0
  else
    return 1
  fi
}

function ready() {
  if STATS="$(${CURL_CMD} "${GRAFANA_URL}/api/admin/stats")" &&
    [ "$(jq -er .orgs <<<"${STATS}")" -eq 2 ] &&
    [ "$(jq -er .dashboards <<<"${STATS}")" -ge "$(($(find /asystem/etc/dashboards \( -path "*/public/*" -o -path "*/private/*" \) -name "graph_*\.jsonnet" | wc -l) + 8))" ]; then
    return 0
  else
    return 1
  fi
}

[ "$#" -eq 1 ] && [ "${1}" == "alive" ] && exit $(alive)
exit $(ready)
