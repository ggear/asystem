curl -sf -H "Authorization: Bearer ${HOMEASSISTANT_API_TOKEN}" "http://${HOMEASSISTANT_SERVICE}:${HOMEASSISTANT_HTTP_PORT}/api/" | jq -er '.message == "API running."' >/dev/null
