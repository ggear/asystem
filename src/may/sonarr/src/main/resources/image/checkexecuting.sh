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
  set -x
else
  alias curl="curl -sf --connect-timeout 2 --max-time 2"
fi

shopt -s expand_aliases

if
  curl -s -X GET "http://${SONARR_SERVICE_PROD}:${SONARR_HTTP_PORT}/api/v3/health" -H "X-Api-Key: ${SONARR_API_KEY}" | jq -e 'length == 0' >/dev/null
then
  set +x
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "✅ The service [sonarr] is executing :)" >&2
  exit 0
else
  set +x
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "❌ The service [sonarr] is *NOT* executing :(" >&2
  exit 1
fi
