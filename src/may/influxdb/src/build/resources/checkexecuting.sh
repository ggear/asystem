/asystem/etc/checkalive.sh "${POSITIONAL_ARGS[@]}" &&
  [ "$(influx ping --host http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT} 2>&1)" == "OK" ]
