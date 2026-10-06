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
  HEALTHCHECK_SECRETS=()
  for HEALTHCHECK_NAME in $(compgen -e); do
    HEALTHCHECK_VALUE="${!HEALTHCHECK_NAME}"
    if [[ "${HEALTHCHECK_NAME}" =~ (^|_)(TOKEN|KEY|PASSWORD|SECRET)(_|$) ]] && [ "${#HEALTHCHECK_VALUE}" -ge 4 ]; then
      HEALTHCHECK_SECRETS+=("${HEALTHCHECK_VALUE}")
    fi
  done
  exec {HEALTHCHECK_TRACE}> >(while IFS= read -r LINE; do for SECRET in "${HEALTHCHECK_SECRETS[@]}"; do LINE="${LINE//"${SECRET}"/********}"; done; printf '%s\n' "${LINE}"; done >&2)
  HEALTHCHECK_TRACER=$!
  BASH_XTRACEFD=${HEALTHCHECK_TRACE}
  set -x
else
  alias curl="curl -sf --connect-timeout 2 --max-time 2"
fi

shopt -s expand_aliases

if
  /asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" && last=$(mosquitto_sub -h "$VERNEMQ_SERVICE" -p "$VERNEMQ_API_PORT" -t 'zigbee/Deck Fans Outlet' -W 1 2>/dev/null | jq -r '.last_seen // empty' 2>/dev/null | sed 's/T/ /; s/+.*//' | sort | tail -n 1) && [ -n "$last" ] && [ $(($(date +%s) - $(date -d "$last" +%s 2>/dev/null || echo 0))) -lt 3660 ] && last=$(mosquitto_sub -h "$VERNEMQ_SERVICE" -p "$VERNEMQ_API_PORT" -t 'zigbee/Kitchen Fan Outlet' -W 1 2>/dev/null | jq -r '.last_seen // empty' 2>/dev/null | sed 's/T/ /; s/+.*//' | sort | tail -n 1) && [ -n "$last" ] && [ $(($(date +%s) - $(date -d "$last" +%s 2>/dev/null || echo 0))) -lt 3660 ]
then
  set +x
  [ "${HEALTHCHECK_VERBOSE}" == true ] && exec {HEALTHCHECK_TRACE}>&- && wait "${HEALTHCHECK_TRACER}"
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "✅ The service [zigbee2mqtt] is healthy :)" >&2
  exit 0
else
  set +x
  [ "${HEALTHCHECK_VERBOSE}" == true ] && exec {HEALTHCHECK_TRACE}>&- && wait "${HEALTHCHECK_TRACER}"
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "❌ The service [zigbee2mqtt] is *NOT* healthy :(" >&2
  exit 1
fi
