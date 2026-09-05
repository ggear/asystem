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
  local script="$1" label="$2" interval="$3" timeout="$4" waited=0 grace=5 report=30
  ((interval > 0)) || interval=1
  echo "Waiting for service to ${label} ..."
  while ! "${ASYSTEM_HOME}/${script}" >/dev/null 2>&1; do
    if ((waited >= timeout)); then
      echo "Waiting for service to ${label} ... failed after [${waited}] of [${timeout}] seconds"
      "${ASYSTEM_HOME}/${script}" -v 2>&1 | tail -n 5
      echo "ERROR: Service failed to ${label} within [${timeout}] seconds" >&2
      exit 1
    fi
    if ((waited == grace)) || ((waited > 0 && waited % report == 0)); then
      echo "Waiting for service to ${label} ... waited [${waited}] of [${timeout}] seconds"
      "${ASYSTEM_HOME}/${script}" -v 2>&1 | tail -n 3
    fi
    sleep "${interval}"
    waited=$((waited + interval))
  done
  echo "Waiting for service to ${label} ... done after [${waited}] of [${timeout}] seconds"
}

wait_service "checkalive.sh" "come alive" 1 "${SERVICE_WAIT_ALIVE_SECONDS}"

echo "--------------------------------------------------------------------------------"
echo "Bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

echo 'InfluxDB initialised'

echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"

wait_service "checkexecuting.sh" "start executing" 1 "${SERVICE_WAIT_EXECUTING_SECONDS}"
echo "----------" && echo "✅ Service has started"