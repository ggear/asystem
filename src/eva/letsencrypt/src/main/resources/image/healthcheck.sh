#!/bin/bash

set -eo pipefail

HEALTHCHECK_VERBOSE=${HEALTHCHECK_VERBOSE:-false}
if [ "${HEALTHCHECK_VERBOSE}" == true ]; then
  set -o xtrace
fi

function alive() {
  if [ $(ps uax | grep dnsrobocert | grep -v grep | wc -l) -eq 1 ]; then
    return 0
  else
    return 1
  fi
}

function ready() {
  if [ $(ps uax | grep dnsrobocert | grep -v grep | wc -l) -eq 1 ] &&
    [ $((($(date +%s) - $(stat /etc/letsencrypt/logs/letsencrypt.log -c %Y)) / 3600)) -le 13 ] &&
    [ $(grep ERROR /etc/letsencrypt/logs/letsencrypt.log | wc -l) -eq 0 ]; then
    return 0
  else
    return 1
  fi
}

[ "$#" -eq 1 ] && [ "${1}" == "alive" ] && exit $(alive)
exit $(ready)
