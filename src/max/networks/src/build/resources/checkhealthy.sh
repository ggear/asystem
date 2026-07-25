/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  mosquitto_sub -h "$BROKER_HOST" -p "$BROKER_PORT" ${BROKER_TOKEN:+-u networks -P $BROKER_TOKEN} -t "networks/data/+" -W 2 2>/dev/null | jq -e -s 'length > 0 and all(.[]; .status != "dead")' >/dev/null
