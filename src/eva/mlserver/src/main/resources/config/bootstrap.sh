#!/bin/sh

echo "--------------------------------------------------------------------------------"
echo "Bootstrap initialising ..."
echo "--------------------------------------------------------------------------------"

while ! curl -sf http://${MLSERVER_SERVICE}:${MLSERVER_HTTP_PORT} >/dev/null 2>&1; do
  echo "Waiting for service to come alive ..." && sleep 1
done

set -eo pipefail

echo "--------------------------------------------------------------------------------"
echo "Bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"