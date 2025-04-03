#!/bin/bash

echo "--------------------------------------------------------------------------------"
echo "Service is starting ..."
echo "--------------------------------------------------------------------------------"

ASYSTEM_HOME=${ASYSTEM_HOME:-"/asystem/etc"}

MESSAGE="Waiting for service to come alive ..."
echo "${MESSAGE}"
while ! "${ASYSTEM_HOME}/checkalive.sh"; do
 echo "${MESSAGE}" && sleep 1
done

set -eo pipefail

echo "--------------------------------------------------------------------------------"
echo "Bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

# TODO: Work out if a REST API exists to create databases, else raise feature request for REST API doc or HTTP_BIND_ADDRESS respect, or both
[ $(curl -sf "http://${INFLUXDB3_SERVICE}:${INFLUXDB3_API_PORT}/api/v3/configure/database?format=csv&show_deleted=false" | grep -c host_private) -eq 0 ] && echo "Need to create database from outside of host!"

echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"

set +eo pipefail

MESSAGE="Waiting for service to become ready ..."
echo "${MESSAGE}"
while ! "${ASYSTEM_HOME}/checkready.sh"; do
  echo "${MESSAGE}" && sleep 1
done
echo "----------" && echo "Service has started"