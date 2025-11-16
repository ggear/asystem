/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  ts=$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ") && curl -s -X POST -H "Authorization: Bearer ${HOMEASSISTANT_API_TOKEN}" -H "Content-Type: application/json" -d '{"event_type":"postgres_test","event_data":{"ts":"'"$ts"'"}}' "http://${HOMEASSISTANT_SERVICE}:${HOMEASSISTANT_HTTP_PORT}/api/events" >/dev/null &&
  curl -s -H "Authorization: Bearer ${HOMEASSISTANT_API_TOKEN}" "http://${HOMEASSISTANT_SERVICE}:${HOMEASSISTANT_HTTP_PORT}/api/history/period/$ts?filter_entity_id=none" | jq -e 'length > 0' >/dev/null &&
  curl -s -H "Authorization: Bearer ${HOMEASSISTANT_API_TOKEN}" -H "Content-Type: application/json" "http://${HOMEASSISTANT_SERVICE}:${HOMEASSISTANT_HTTP_PORT}/api/hassio/addons" | jq -e '.data.addons[] | select(.slug=="core_influxdb")' >/dev/null &&
  ! grep -Eq '^10\.0\.[0-9]+\.[0-9]+:' /config/ip_bans.yaml 2>/dev/null
