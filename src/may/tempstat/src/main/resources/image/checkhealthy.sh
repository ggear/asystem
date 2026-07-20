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
  /asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" && PAYLOAD=$(mosquitto_sub -h "$BROKER_HOST" -p "$BROKER_PORT" ${BROKER_TOKEN:+-u tempstat -P $BROKER_TOKEN} -t "tempstat/data" -C 1 -W 2 2>/dev/null) && jq -e '(.samples | length) == 3' <<<"$PAYLOAD" >/dev/null && TIMESTAMP=$(jq -r '.timestamp' <<<"$PAYLOAD") && (($(date +%s) - $(date -d "$TIMESTAMP" +%s) < 1200))
then
  set +x
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "✅ The service [tempstat] is healthy :)" >&2
  exit 0
else
  set +x
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "❌ The service [tempstat] is *NOT* healthy :(" >&2
  exit 1
fi
