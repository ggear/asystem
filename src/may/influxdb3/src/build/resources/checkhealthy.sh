/asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" &&
  [ "$(influxdb3 query --format json --database "${INFLUXDB3_DATABASE_HOME}" "SELECT 1" 2>/dev/null | jq -e '.[0]["Int64(1)"]')" == "1" ] &&
  [ "$(influxdb3 query --format json --database "${INFLUXDB3_DATABASE_HOME}" --token "${INFLUXDB3_TOKEN_HOME}" "SELECT 1" 2>/dev/null | jq -e '.[0]["Int64(1)"]')" == "1" ] &&
  floor="$(influxdb3 query --format json --database "${INFLUXDB3_DATABASE_HOME}" --token "${INFLUXDB3_TOKEN_HOME}" "SELECT CAST(min(time) AS BIGINT) AS floor FROM sensor__temperature" 2>/dev/null | jq -r '.[0].floor' || true)" &&
  floor="${floor:-null}" &&
  { [ ! -s /tmp/influxdb3_floor ] || { [ "${floor}" != "null" ] && [ "${floor}" -le "$(cat /tmp/influxdb3_floor)" ]; }; } &&
  { [ "${floor}" = "null" ] || echo "${floor}" >/tmp/influxdb3_floor; }
