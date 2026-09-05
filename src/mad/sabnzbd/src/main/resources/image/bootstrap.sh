#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

echo "--------------------------------------------------------------------------------"
echo "Service is starting ..."
echo "--------------------------------------------------------------------------------"

ASYSTEM_HOME=${ASYSTEM_HOME:-"/asystem/etc"}

SERVICE_WAIT_ALIVE_SECONDS=900
SERVICE_WAIT_EXECUTING_SECONDS=900

wait_service() {
  local script="$1" label="$2" interval="$3" timeout="$4" waited=0
  ((interval > 0)) || interval=1
  while ! "${ASYSTEM_HOME}/${script}" >/dev/null 2>&1; do
    if ((waited >= timeout)); then
      echo "Waiting for service to ${label} ... failed [${waited}s/${timeout}s]"
      "${ASYSTEM_HOME}/${script}" -v 2>&1 | tail -n 5
      echo "ERROR: Service failed to ${label} within [${timeout}] seconds" >&2
      exit 1
    fi
    if ((waited % 30 == 0)); then
      echo "Waiting for service to ${label} ... [${waited}s/${timeout}s]"
      "${ASYSTEM_HOME}/${script}" -v 2>&1 | tail -n 3
    fi
    sleep "${interval}"
    waited=$((waited + interval))
  done
  echo "Waiting for service to ${label} ... done [${waited}s/${timeout}s]"
}

wait_service "checkalive.sh" "come alive" 1 "${SERVICE_WAIT_ALIVE_SECONDS}"

echo "--------------------------------------------------------------------------------"
echo "Bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

# TODO: Provide implementation
echo ''

echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"

wait_service "checkexecuting.sh" "start executing" 1 "${SERVICE_WAIT_EXECUTING_SECONDS}"
echo "----------" && echo "✅ Service has started"