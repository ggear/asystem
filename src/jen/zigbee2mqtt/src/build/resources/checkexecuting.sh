/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  awk -v port="$(printf '%04X' "$VERNEMQ_API_PORT")" '$4 == "01" && substr($3, index($3, ":") + 1) == port { found = 1 } END { exit !found }' /proc/net/tcp /proc/net/tcp6 &&
  mosquitto_sub -h "$VERNEMQ_SERVICE" -p "$VERNEMQ_API_PORT" -t 'zigbee/bridge/state' -W 1 2>/dev/null | jq -e '.state == "online"' >/dev/null
