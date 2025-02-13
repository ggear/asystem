#!/bin/bash

echo "--------------------------------------------------------------------------------"
echo "Bootstrap initialising ..."
echo "--------------------------------------------------------------------------------"

while ! "/asystem/etc/healthcheck.sh" alive; do
  echo "Waiting for service to come alive ..." && sleep 1
done

echo "--------------------------------------------------------------------------------"
echo "Bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

while ! "/asystem/etc/healthcheck.sh"; do
  echo "Waiting for service to become ready ..." && sleep 1
done

echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"
