#!/bin/bash

if [ "${TEMPSTAT_MOCK}" = "1" ]; then
  socat pty,raw,echo=0,wait-slave,link=/dev/ttyUSB0 exec:/asystem/bin/mockdev &
  for _ in $(seq 1 50); do
    [ -e /dev/ttyUSB0 ] && break
    sleep 0.1
  done
fi

exec /asystem/bin/tempstat --poll-period "${TEMPSTAT_POLL_PERIOD}" --log-level "${TEMPSTAT_LOG_LEVEL}" "$@"
