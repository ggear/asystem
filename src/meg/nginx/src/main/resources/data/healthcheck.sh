#!/bin/sh

HEALTHCHECK_VERBOSE=${HEALTHCHECK_VERBOSE:-false}
if [ "${HEALTHCHECK_VERBOSE}" = true ]; then
  CURL_CMD="curl -f --connect-timeout 2 --max-time 2"
  set -o xtrace
else
  CURL_CMD="curl -sf --connect-timeout 2 --max-time 2"
fi

alive() {
  if [ "$(curl -I http://localhost | grep HTTP | wc -l)" -eq 1 ]; then
    return 0
  else
    return 1
  fi
}
ready() {
  if [ "$(curl -I https://nginx.janeandgraham.com | grep HTTP | cut -d ' ' -f2)" = "200" ]; then
    return 0
  else
    return 1
  fi
}
if [ "$#" -eq 1 ] && [ "${1}" = "alive" ]; then alive; else ready; fi
exit $?
