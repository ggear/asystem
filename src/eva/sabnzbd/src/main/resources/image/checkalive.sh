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
  [ "$(curl "http://${SABNZBD_SERVICE_PROD}:${SABNZBD_HTTP_PORT}/sabnzbd/api?output=json&apikey=${SABNZBD_API_KEY}&mode=status&skip_dashboard=0" | jq -er '.pid')" -gt 0 ]
then
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "The service [sabnzbd] is alive :)" >&2
  exit 0
else
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "The service [sabnzbd] is *NOT* alive :(" >&2
  exit 1
fi
