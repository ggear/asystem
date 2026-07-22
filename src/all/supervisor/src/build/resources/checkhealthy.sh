/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  curl -sf --unix-socket /var/run/docker.sock --max-time 2 "http://localhost/_ping" | grep -q "^OK$" &&
  PAYLOAD=$(mosquitto_sub -h "$BROKER_HOST" -p "$BROKER_PORT" ${BROKER_TOKEN:+-u supervisor -P $BROKER_TOKEN} -t "supervisor/${SUPERVISOR_HOST}/data/host" -C 1 -W 2 2>/dev/null) && jq -e '.pulse.ok == true' <<<"$PAYLOAD" >/dev/null && TIMESTAMP=$(jq -r '.timestamp' <<<"$PAYLOAD") && (($(date +%s) - TIMESTAMP < 1200)) &&
  PAYLOAD=$(mosquitto_sub -h "$BROKER_HOST" -p "$BROKER_PORT" ${BROKER_TOKEN:+-u supervisor -P $BROKER_TOKEN} -t "supervisor/${SUPERVISOR_HOST}/data/service/supervisor" -C 1 -W 2 2>/dev/null) && jq -e '.pulse.ok == true' <<<"$PAYLOAD" >/dev/null
