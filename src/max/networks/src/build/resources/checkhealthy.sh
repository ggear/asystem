/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  PAYLOADS=$(mosquitto_sub -h "$BROKER_HOST" -p "$BROKER_PORT" ${BROKER_TOKEN:+-u networks -P $BROKER_TOKEN} -t "networks/data/+" -W 2 2>/dev/null | jq -s -c .) &&
  jq -e --argjson now "$(date +%s)" 'length > 0 and all(.[]; (.ok | type) == "boolean" and (.score | type) == "number" and (.status | IN("fit", "sick", "dead")) and ($now - .timestamp) < 1200)' <<<"$PAYLOADS" >/dev/null
