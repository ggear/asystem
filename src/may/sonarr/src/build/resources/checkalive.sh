curl -s -o >(jq -e '.status == "OK"' >/dev/null) -w "%{http_code}" "http://${SONARR_SERVICE_PROD}:${SONARR_HTTP_PORT}/ping" -H "X-Api-Key: ${SONARR_API_KEY}" | grep -q '^200$'
