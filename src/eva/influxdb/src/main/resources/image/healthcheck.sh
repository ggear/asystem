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
  if [ "$(influx ping --host http://localhost:${INFLUXDB_HTTP_PORT} >/dev/null 2>&1)" == "OK" ]; then
    return 0
  else
    return 1
  fi
}

function ready() {
  if [ "$(influx ping --host http://localhost:${INFLUXDB_HTTP_PORT} >/dev/null 2>&1)" == "OK" ] &&
    [ "$(${CURL_CMD} "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN}" --data-urlencode "db=${INFLUXDB_BUCKET_HOME_PUBLIC}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" -eq 0 ] &&
    [ "$(${CURL_CMD} "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN}" --data-urlencode "db=${INFLUXDB_BUCKET_HOME_PRIVATE}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" -eq 0 ] &&
    [ "$(${CURL_CMD} "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN}" --data-urlencode "db=${INFLUXDB_BUCKET_DATA_PUBLIC}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" -eq 0 ] &&
    [ "$(${CURL_CMD} "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN}" --data-urlencode "db=${INFLUXDB_BUCKET_DATA_PRIVATE}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" -eq 0 ] &&
    [ "$(${CURL_CMD} "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN}" --data-urlencode "db=${INFLUXDB_BUCKET_HOST_PRIVATE}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" -eq 0 ] &&
    [ "$(${CURL_CMD} "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PUBLIC}:${INFLUXDB_TOKEN_PUBLIC_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_HOME_PUBLIC}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" -eq 0 ] &&
    [ "$(${CURL_CMD} "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PUBLIC}:${INFLUXDB_TOKEN_PUBLIC_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_DATA_PUBLIC}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" -eq 0 ] &&
    [ "$(${CURL_CMD} "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN_PRIVATE_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_HOME_PUBLIC}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" -eq 0 ] &&
    [ "$(${CURL_CMD} "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN_PRIVATE_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_HOME_PRIVATE}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" -eq 0 ] &&
    [ "$(${CURL_CMD} "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN_PRIVATE_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_DATA_PUBLIC}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" -eq 0 ] &&
    [ "$(${CURL_CMD} "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN_PRIVATE_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_DATA_PRIVATE}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" -eq 0 ] &&
    [ "$(${CURL_CMD} "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN_PRIVATE_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_HOST_PRIVATE}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" -eq 0 ]; then
    echo return 0
  else
    echo return 1
  fi
}

[ "$#" -eq 1 ] && [ "${1}" == "alive" ] && exit $(alive)
exit $(ready)
