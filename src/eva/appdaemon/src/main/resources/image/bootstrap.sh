#!/bin/bash

echo "--------------------------------------------------------------------------------"
echo "Service is starting ..."
echo "--------------------------------------------------------------------------------"

ASYSTEM_HOME=${ASYSTEM_HOME:-"/asystem/etc"}

while ! "${ASYSTEM_HOME}/healthcheck.sh" alive; do
  echo "Waiting for service to come alive ..." && sleep 1
done

set -eo pipefail

echo "--------------------------------------------------------------------------------"
echo "Bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

echo ''

echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"

set +eo pipefail

while ! "${ASYSTEM_HOME}/healthcheck.sh"; do
  echo "Waiting for service to become ready ..." && sleep 1
done
echo "----------" && echo "Service has started"