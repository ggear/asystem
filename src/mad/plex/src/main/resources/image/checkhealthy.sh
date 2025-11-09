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
  /asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" && [ "$(find /share -mindepth 1 -maxdepth 1 | wc -l)" -eq "$(find /share -mindepth 2 -maxdepth 2 -name media -type d | wc -l)" ] && [ "$(curl -sf "http://${PLEX_SERVICE}:${PLEX_HTTP_PORT}/library/sections?X-Plex-Token=${PLEX_TOKEN}" | xq '.MediaContainer.Location | length' 2>/dev/null)" -gt 0 ] && [ "$(curl -sf "http://${PLEX_SERVICE}:${PLEX_HTTP_PORT}/library/sections?X-Plex-Token=${PLEX_TOKEN}" | xq '.MediaContainer.Location[]."@path"' 2>/dev/null | jq 'length')" -eq "$(find /share -mindepth 4 -maxdepth 4 -path '*/media/*' ! -path '*audio*' -type d | wc -l)" ]
then
  set +x
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "✅ The service [plex] is healthy :)" >&2
  exit 0
else
  set +x
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "❌ The service [plex] is *NOT* healthy :(" >&2
  exit 1
fi
