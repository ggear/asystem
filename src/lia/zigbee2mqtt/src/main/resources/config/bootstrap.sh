#!/bin/sh

echo "--------------------------------------------------------------------------------"
echo "Bootstrap initialising ..."
echo "--------------------------------------------------------------------------------"

while [ $(mosquitto_sub -h ${VERNEMQ_SERVICE} -p ${VERNEMQ_PORT} -t 'zigbee/bridge/state' -W 1 2>/dev/null | grep online | wc -l) -ne 1 ]; do
  echo "Waiting for service to come up ..."
  sleep 1
done

set -e
set -o pipefail

echo "--------------------------------------------------------------------------------"
echo "Bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

# TODO: Re-enable once zigbee network has been healed
#/app/data/mqtt_config.sh

echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"
