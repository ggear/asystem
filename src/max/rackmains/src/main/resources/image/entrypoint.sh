#!/bin/bash

DRY_RUN=()
if [ "${RACKMAINS_MOCK}" = "1" ]; then
  DRY_RUN=(--dry-run)
  /asystem/bin/mockdriver "${RACKMAINS_DEVICE}" &
  for _ in $(seq 1 50); do
    [ -S "${RACKMAINS_DEVICE}" ] && break
    sleep 0.1
  done
fi

exec /asystem/bin/rackmains serve "${DRY_RUN[@]}" --poll-period "${RACKMAINS_POLL_PERIOD}" --log-level "${RACKMAINS_LOG_LEVEL}" \
  --device "${RACKMAINS_DEVICE}" "$@"
