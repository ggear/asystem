[ $(curl -X GET http://${SONARR_SERVICE_PROD}:${SONARR_HTTP_PORT}/api/v3/health  -H "X-Api-Key: ${SONARR_API_KEY}" | jq 'length == 0') == "true" ]
