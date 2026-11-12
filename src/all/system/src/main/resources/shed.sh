#!/bin/bash

set -Eeuo pipefail

# Forced command for the rackmains key. Dispatches on SSH_ORIGINAL_COMMAND and runs exactly the three calls the guard makes.

case "${SSH_ORIGINAL_COMMAND:-}" in
"asleep --deep")
  exec /usr/local/bin/asleep --deep
  ;;
"asleep --shallow --except rackmains")
  STOP_ARGUMENTS=()
  CONTAINERS="$(docker ps --format '{{.Names}}')"
  if grep -qx supervisor <<<"${CONTAINERS}"; then
    STOP_ARGUMENTS+=(--stop supervisor)
  fi
  while IFS= read -r CONTAINER; do
    [[ -n "${CONTAINER}" && "${CONTAINER}" != "supervisor" && "${CONTAINER}" != "rackmains" ]] && STOP_ARGUMENTS+=(--stop "${CONTAINER}")
  done <<<"${CONTAINERS}"
  exec /usr/local/bin/asleep --shallow "${STOP_ARGUMENTS[@]}"
  ;;
"awake")
  exec /usr/local/bin/awake
  ;;
*)
  echo "rackmains-shed command not allowed [${SSH_ORIGINAL_COMMAND:-}]" >&2
  exit 2
  ;;
esac
