curl -s -X GET "http://${SONARR_SERVICE_PROD}:${SONARR_HTTP_PORT}/api/v3/health" -H "X-Api-Key: ${SONARR_API_KEY}" | jq -e 'length == 0' >/dev/null
