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

curl -sf -X GET http://${SONARR_SERVICE_PROD}:${SONARR_HTTP_PORT}/api/v3/indexer -H "X-Api-Key: ${SONARR_API_KEY}"

#curl -X POST http://${SONARR_SERVICE_PROD}:${SONARR_HTTP_PORT}/api/v3/indexer -H "X-Api-Key: ${SONARR_API_KEY}" -H "Content-Type: application/json" -d '
#  {
#    "name": "NZBgeek",
#    "enableRss": true,
#    "enableAutomaticSearch": true,
#    "enableInteractiveSearch": true,
#    "supportsRss": true,
#    "supportsSearch": true,
#    "protocol": "usenet",
#    "priority": 25,
#    "implementation": "Newznab",
#    "configContract": "NewznabSettings",
#    "tags": [],
#    "fields": [
#      {
#        "name": "baseUrl",
#        "value": "https://api.nzbgeek.info"
#      },
#      {
#        "name": "apiKey",
#        "value": "'"${GEEK_KEY}"'"
#      }
#    ]
#  }
#'

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