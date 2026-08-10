/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  [ "$(curl "http://${UNPOLLER_SERVICE}:${UNPOLLER_HTTP_PORT}/api/v1/output/influxdb/events" | jq -er .influxdb.latest | cut -d 'T' -f 1)" == "$(date --rfc-3339=ns | sed 's/ /T/' | cut -d 'T' -f 1)" ]
