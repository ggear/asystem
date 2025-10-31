[ "$(influxdb3 query --format json --database "${INFLUXDB3_DATABASE_HOME_PUBLIC}" "SELECT 1" 2>/dev/null | jq -e '.[0]["Int64(1)"]')" == "1" ] &&
  [ "$(influxdb3 query --format json --database "${INFLUXDB3_DATABASE_DATA_PUBLIC}" "SELECT 1" 2>/dev/null | jq -e '.[0]["Int64(1)"]')" == "1" ] &&
  [ "$(influxdb3 query --format json --database "${INFLUXDB3_DATABASE_HOME_PRIVATE}" "SELECT 1" 2>/dev/null | jq -e '.[0]["Int64(1)"]')" == "1" ] &&
  [ "$(influxdb3 query --format json --database "${INFLUXDB3_DATABASE_HOST_PRIVATE}" "SELECT 1" 2>/dev/null | jq -e '.[0]["Int64(1)"]')" == "1" ] &&
  [ "$(influxdb3 query --format json --database "${INFLUXDB3_DATABASE_HOME_PUBLIC}" --token "${INFLUXDB3_TOKEN_PUBLIC}" "SELECT 1" 2>/dev/null | jq -e '.[0]["Int64(1)"]')" == "1" ] &&
  [ "$(influxdb3 query --format json --database "${INFLUXDB3_DATABASE_DATA_PUBLIC}" --token "${INFLUXDB3_TOKEN_PUBLIC}" "SELECT 1" 2>/dev/null | jq -e '.[0]["Int64(1)"]')" == "1" ] &&
  [ "$(influxdb3 query --format json --database "${INFLUXDB3_DATABASE_HOME_PRIVATE}" --token "${INFLUXDB3_TOKEN_PRIVATE}" "SELECT 1" 2>/dev/null | jq -e '.[0]["Int64(1)"]')" == "1" ] &&
  [ "$(influxdb3 query --format json --database "${INFLUXDB3_DATABASE_HOST_PRIVATE}" --token "${INFLUXDB3_TOKEN_PRIVATE}" "SELECT 1" 2>/dev/null | jq -e '.[0]["Int64(1)"]')" == "1" ]
