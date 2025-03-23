#!/bin/bash

set -eo pipefail

HEALTHCHECK_VERBOSE=${HEALTHCHECK_VERBOSE:-false}
if [ "${HEALTHCHECK_VERBOSE}" == true ]; then
  set -o xtrace
fi

function alive() {
  if [ -f "/data/html/loopdata/loop-data.txt" ]; then
    return 0
  else
    return 1
  fi
}

function ready() {
  if [ -f "/data/html/loopdata/loop-data.txt" ] &&
    [ $(($(date +%s) - $(stat "/data/html/loopdata/loop-data.txt" -c %Y))) -le 2 ] &&
    [ $(($(date +%s) - $(jq -r '."current.dateTime.raw"' "/data/html/loopdata/loop-data.txt"))) -le 2 ] &&
    [ -n "$(jq -r '."current.outTemp" | select( . != null )' "/data/html/loopdata/loop-data.txt")" ]; then
    echo return 0
  else
    echo return 1
  fi
}

[ "$#" -eq 1 ] && [ "${1}" == "alive" ] && exit $(alive)
exit $(ready)
