/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  ! grep -Eq '^10\.0\.[0-9]+\.[0-9]+:' /config/ip_bans.yaml 2>/dev/null &&
  curl -s -H "Authorization: Bearer ${HOMEASSISTANT_API_TOKEN}" -H "Content-Type: application/json" "http://${HOMEASSISTANT_SERVICE}:${HOMEASSISTANT_HTTP_PORT}/api/history/period?filter_entity_id=input_boolean.home_started" | jq -e 'length > 0' >/dev/null
