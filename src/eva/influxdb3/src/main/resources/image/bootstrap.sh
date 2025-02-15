#!/bin/bash

echo "--------------------------------------------------------------------------------"
echo "Bootstrap initialising ..."
echo "--------------------------------------------------------------------------------"

while ! "/asystem/etc/healthcheck.sh" alive; do
  echo "Waiting for service to come alive ..." && sleep 1
done

set -eo pipefail

echo "--------------------------------------------------------------------------------"
echo "Bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

[[ $(influxdb3 show databases | grep -c host_private) -eq 0 ]] && influxdb3 create database host_private

echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"
