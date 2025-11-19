/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  mosquitto_sub -h "$VERNEMQ_SERVICE" -p "$VERNEMQ_API_PORT" -t 'zigbee/bridge/health' -W 1 2>/dev/null | jq -r '.process.uptime_sec as $u | (.devices|length) as $d | if ($u>0 and $d>0) then 0 else 1 end' | awk '{exit $1}'
