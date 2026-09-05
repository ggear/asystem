/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  [ "$(influxdb3 query --format json --database "${INFLUXDB3_DATABASE_HOME}" "SELECT 1" 2>/dev/null | jq -e '.[0]["Int64(1)"]')" == "1" ] &&
  [ "$(influxdb3 query --format json --database "${INFLUXDB3_DATABASE_HOME}" --token "${INFLUXDB3_TOKEN_HOME}" "SELECT 1" 2>/dev/null | jq -e '.[0]["Int64(1)"]')" == "1" ]
