#!/bin/bash

set -eo pipefail

HEALTHCHECK_VERBOSE=${HEALTHCHECK_VERBOSE:-false}
if [ "${HEALTHCHECK_VERBOSE}" == true ]; then
  CURL_CMD="curl -f --connect-timeout 2 --max-time 2"
  set -o xtrace
else
  CURL_CMD="curl -sf --connect-timeout 2 --max-time 2"
fi

function alive() {
  if ALIVE=$(influx ping --host http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT} 2>&1) &&
    [ "${ALIVE}" == "OK" ]; then
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "Alive :)") || return 0
  else
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "NOT Alive :(") || return 1
  fi
}
function ready() {
  if [ "$(influx ping --host http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT})" == "OK" ] &&
    influx query 'from(bucket:"'"${INFLUXDB_BUCKET_HOME_PUBLIC}"'") |> range(start:-15m) |> filter(fn: (r) => r["_measurement"] == "a_non_existent_metric")' &&
    influx query 'from(bucket:"'"${INFLUXDB_BUCKET_HOME_PRIVATE}"'") |> range(start:-15m) |> filter(fn: (r) => r["_measurement"] == "a_non_existent_metric")' &&
    influx query 'from(bucket:"'"${INFLUXDB_BUCKET_DATA_PUBLIC}"'") |> range(start:-15m) |> filter(fn: (r) => r["_measurement"] == "a_non_existent_metric")' &&
    influx query 'from(bucket:"'"${INFLUXDB_BUCKET_DATA_PRIVATE}"'") |> range(start:-15m) |> filter(fn: (r) => r["_measurement"] == "a_non_existent_metric")' &&
    influx query 'from(bucket:"'"${INFLUXDB_BUCKET_HOST_PRIVATE}"'") |> range(start:-15m) |> filter(fn: (r) => r["_measurement"] == "a_non_existent_metric")' &&
    [ "$(${CURL_CMD} "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PUBLIC}:${INFLUXDB_TOKEN_PUBLIC_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_HOME_PUBLIC}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" == "0" ] &&
    [ "$(${CURL_CMD} "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PUBLIC}:${INFLUXDB_TOKEN_PUBLIC_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_DATA_PUBLIC}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" == "0" ] &&
    [ "$(${CURL_CMD} "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN_PRIVATE_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_HOME_PUBLIC}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" == "0" ] &&
    [ "$(${CURL_CMD} "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN_PRIVATE_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_HOME_PRIVATE}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" == "0" ] &&
    [ "$(${CURL_CMD} "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN_PRIVATE_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_DATA_PUBLIC}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" == "0" ] &&
    [ "$(${CURL_CMD} "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN_PRIVATE_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_DATA_PRIVATE}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" == "0" ] &&
    [ "$(${CURL_CMD} "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN_PRIVATE_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_HOST_PRIVATE}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" == "0" ]; then
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "Alive :)") || return 0
  else
    ([ "${HEALTHCHECK_VERBOSE}" == true ] && echo "NOT Alive :(") || return 1
  fi

[ "$#" -eq 1 ] && [ "${1}" == "alive" ] && exit $(alive)
exit $(ready)
