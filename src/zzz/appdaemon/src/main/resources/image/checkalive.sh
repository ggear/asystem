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
  [ "$(curl -LI "https://${APPDAEMON_SERVICE}:${APPDAEMON_HTTP_PORT}/aui/index.html" | tac | tac | head -n 1 | cut -d$' ' -f2)" == "200" ]
then
  set +x
  [ "${HEALTHCHECK_VERBOSE}" == true ] && exec {HEALTHCHECK_TRACE}>&- && wait "${HEALTHCHECK_TRACER}"
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "✅ The service [appdaemon] is alive :)" >&2
  exit 0
else
  set +x
  [ "${HEALTHCHECK_VERBOSE}" == true ] && exec {HEALTHCHECK_TRACE}>&- && wait "${HEALTHCHECK_TRACER}"
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "❌ The service [appdaemon] is *NOT* alive :(" >&2
  exit 1
fi
