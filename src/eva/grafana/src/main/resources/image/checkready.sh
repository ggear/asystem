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

if
  READY="$(curl "${GRAFANA_URL}/api/admin/stats")" && [ "$(jq -er .orgs <<<"${READY}")" -eq 2 ] && [ "$(jq -er .dashboards <<<"${READY}")" -ge "$(($(find /asystem/etc/dashboards \( -path "*/public/*" -o -path "*/private/*" \) -name "graph_*\.jsonnet" | wc -l) + 8))" ]
then
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "The service [grafana] is ready :)" >&2
  exit 0
else
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "The service [grafana] is *NOT* ready :(" >&2
  exit 1
fi
