/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  PAYLOAD=$(mosquitto_sub -h "$BROKER_HOST" -p "$BROKER_PORT" ${BROKER_TOKEN:+-u tempstat -P $BROKER_TOKEN} -t "tempstat/${TEMPSTAT_HOST}/data" -C 1 -W 2 2>/dev/null) && jq -e '(.samples | length) == 3' <<<"$PAYLOAD" >/dev/null && TIMESTAMP=$(jq -r '.timestamp' <<<"$PAYLOAD") && (($(date +%s) - $(date -d "$TIMESTAMP" +%s) < 1200))
