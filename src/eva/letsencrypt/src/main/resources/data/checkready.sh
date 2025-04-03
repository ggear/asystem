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
  [ $(ps uax | grep dnsrobocert | grep -v grep | wc -l) -eq 1 ] && [ $(grep ERROR /etc/letsencrypt/logs/letsencrypt.log | wc -l) -eq 0 ] && [ $((($(date +%s) - $(stat /etc/letsencrypt/logs/letsencrypt.log -c %Y)) / 3600)) -le 25 ]
then
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "The service [letsencrypt] is ready :)" >&2
  exit 0
else
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "The service [letsencrypt] is *NOT* ready :(" >&2
  exit 1
fi
