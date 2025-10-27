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
    POSITIONAL_ARGS+=("$1")
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

if [ "${HEALTHCHECK_VERBOSE}" == true ]; then
  alias curl="curl -f --connect-timeout 2 --max-time 2"
  set -o xtrace
else
  alias curl="curl -sf --connect-timeout 2 --max-time 2"
fi

set -eo pipefail
shopt -s expand_aliases

if
  /asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" && [ -f "/data/html/loopdata/loop-data.txt" ] && [ $(($(date +%s) - $(stat "/data/html/loopdata/loop-data.txt" -c %Y))) -le 2 ] && [ $(($(date +%s) - $(jq -r '."current.dateTime.raw"' "/data/html/loopdata/loop-data.txt"))) -le 2 ]
then
  set +o
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "✅ The service [weewx] is ready :)" >&2
  exit 0
else
  set +o
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "❌ The service [weewx] is *NOT* ready :(" >&2
  exit 1
fi
