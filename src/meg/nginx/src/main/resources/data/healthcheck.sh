#!/bin/sh

HEALTHCHECK_VERBOSE=${HEALTHCHECK_VERBOSE:-false}
if [ "${HEALTHCHECK_VERBOSE}" = true ]; then
  CURL_CMD="curl -f --connect-timeout 2 --max-time 2"
  set -o xtrace
else
  CURL_CMD="curl -sf --connect-timeout 2 --max-time 2"
fi

alive() {
  if [ "$(${CURL_CMD} -I http://localhost | grep HTTP | cut -d ' ' -f2)" = "301" ]; then
    return 0
  else
    return 1
  fi
}

ready() {
  if [ "$(${CURL_CMD} -I https://nginx.janeandgraham.com | grep HTTP | cut -d ' ' -f2)" = "200" ]; then
    return 0
  else
    return 1
  fi
}

[ "$#" -eq 1 ] && [ "${1}" = "alive" ] && exit $(alive)
exit $(ready)
