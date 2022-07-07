#!/bin/sh

echo "--------------------------------------------------------------------------------"
echo "Bootstrap initialising ..."
echo "--------------------------------------------------------------------------------"

#while ! curl -sf ${GRAFANA_URL}/api/admin/stats >>/dev/null 2>&1; do
#  echo "Waiting for service to come up ..." && sleep 1
#done

set -e
set -o pipefail

echo "--------------------------------------------------------------------------------"
echo "Bootstrap starting ..."
echo "--------------------------------------------------------------------------------"

# TODO: Implement
# /bootstrap/entity_metadata_publish.sh

echo "--------------------------------------------------------------------------------"
echo "Bootstrap finished"
echo "--------------------------------------------------------------------------------"
