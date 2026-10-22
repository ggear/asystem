/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  { mosquitto_sub -h "$VERNEMQ_SERVICE" -p "$VERNEMQ_API_PORT" -t 'zigbee/bridge/response/health_check' -C 1 -W 5 2>/dev/null & sleep 1 && mosquitto_pub -h "$VERNEMQ_SERVICE" -p "$VERNEMQ_API_PORT" -t 'zigbee/bridge/request/health_check' -m '{}' 2>/dev/null; wait; } | jq -e '.status == "ok" and .data.healthy' >/dev/null &&
  mosquitto_sub -h "$VERNEMQ_SERVICE" -p "$VERNEMQ_API_PORT" -t 'zigbee/bridge/state' -W 1 2>/dev/null | jq -e '.state == "online"' >/dev/null
