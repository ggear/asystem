#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

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
  [ $(curl -sf "http://${PLEX_SERVICE}:${PLEX_HTTP_PORT}/identity" | xq -e '/MediaContainer/@claimed') == "1" ] && [ $(find /share -mindepth 1 -maxdepth 1 | wc -l) -eq $(find /share -mindepth 2 -maxdepth 2 -name media -type d | wc -l) ]
then
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "✅ The service [plex] is ready :)" >&2
  exit 0
else
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "❌ The service [plex] is *NOT* ready :(" >&2
  exit 1
fi
