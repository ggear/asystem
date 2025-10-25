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
  true  #OUTPUT="$(telegraf --test 2>/dev/null)" && #  [ "$(grep -c '^> cpu,cpu=cpu-total,' <<<"${OUTPUT}")" -gt 0 ] && #  [ "$(grep -c '^> mem,host=' <<<"${OUTPUT}")" -gt 0 ] && #  [ "$(grep -c '^> swap,host=' <<<"${OUTPUT}")" -gt 0 ] && #  [ "$(grep -c '^> disk,device=' <<<"${OUTPUT}")" -gt 0 ] && #  [ "$(grep -c '^> diskio,host=' <<<"${OUTPUT}")" -gt 0 ] && #  [ "$(grep -c '^> net,host=' <<<"${OUTPUT}")" -gt 0 ] && #  [ "$(grep -c '^> docker_container_cpu,container_image=' <<<"${OUTPUT}")" -gt 0 ] && #  [ "$(grep -c '^> docker_container_mem,container_image=' <<<"${OUTPUT}")" -gt 0 ] && #  [ "$(grep -c '^> docker_container_blkio,container_image=' <<<"${OUTPUT}")" -gt 0 ] && #  [ "$(grep -c '^> docker_container_net,container_image=' <<<"${OUTPUT}")" -gt 0 ] && #  telegraf --once >/dev/null 2>&1  #telegraf --once >/dev/null 2>&1 && #  [ $(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_API_PORT} -t 'telegraf/macmini-meg/digitemp' -W 1 2>/dev/null | jq -r .tags.run_code) -eq 0 ] && #  [ $(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_API_PORT} -t 'telegraf/macmini-meg/digitemp' -W 1 2>/dev/null | jq -r .fields.metrics_failed) -eq 0 ] && #  [ $(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_API_PORT} -t 'telegraf/macmini-meg/digitemp' -W 1 2>/dev/null | jq -r .fields.metrics_succeeded) -eq 3 ]
then
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "✅ The service [digitemp] is ready :)" >&2
  exit 0
else
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "❌ The service [digitemp] is *NOT* ready :(" >&2
  exit 1
fi
