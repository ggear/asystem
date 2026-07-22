/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  mosquitto_sub -h "$BROKER_HOST" -p "$BROKER_PORT" ${BROKER_TOKEN:+-u supervisor -P $BROKER_TOKEN} -t "supervisor/${SUPERVISOR_HOST}/status" -C 1 -W 2 2>/dev/null | grep -q "^online$"
