#!/bin/bash

POSITIONAL_ARGS=()
HEALTHCHECK_VERBOSE=${HEALTHCHECK_VERBOSE:-false}
while [[ $# -gt 0 ]]; do
  case $1 in
  -v | --verbose)
    HEALTHCHECK_VERBOSE=true
    shift
    ;;
  -h | --help | -*)
    echo "Usage: ${0} [-v|--verbose] [-h|--help] [alive]"
    exit 2
    ;;
  *)
    POSITIONAL_ARGS+=("$1")
    shift
    ;;
  esac
done
set -- "${POSITIONAL_ARGS[@]}"

if [ "${HEALTHCHECK_VERBOSE}" == true ]; then
  alias curl="curl -f --connect-timeout 2 --max-time 2"
  set -o xtrace
else
  alias curl="curl -sf --connect-timeout 2 --max-time 2"
fi

set -eo pipefail
shopt -s expand_aliases

if
  [ "$(influx ping --host http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT})" == "OK" ] && influx query 'from(bucket:"'"${INFLUXDB_BUCKET_HOME_PUBLIC}"'") |> range(start:-15m) |> filter(fn: (r) => r["_measurement"] == "a_non_existent_metric")' && influx query 'from(bucket:"'"${INFLUXDB_BUCKET_HOME_PRIVATE}"'") |> range(start:-15m) |> filter(fn: (r) => r["_measurement"] == "a_non_existent_metric")' && influx query 'from(bucket:"'"${INFLUXDB_BUCKET_DATA_PUBLIC}"'") |> range(start:-15m) |> filter(fn: (r) => r["_measurement"] == "a_non_existent_metric")' && influx query 'from(bucket:"'"${INFLUXDB_BUCKET_DATA_PRIVATE}"'") |> range(start:-15m) |> filter(fn: (r) => r["_measurement"] == "a_non_existent_metric")' && influx query 'from(bucket:"'"${INFLUXDB_BUCKET_HOST_PRIVATE}"'") |> range(start:-15m) |> filter(fn: (r) => r["_measurement"] == "a_non_existent_metric")' && [ "$(curl "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PUBLIC}:${INFLUXDB_TOKEN_PUBLIC_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_HOME_PUBLIC}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" == "0" ] && [ "$(curl "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PUBLIC}:${INFLUXDB_TOKEN_PUBLIC_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_DATA_PUBLIC}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" == "0" ] && [ "$(curl "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN_PRIVATE_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_HOME_PUBLIC}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" == "0" ] && [ "$(curl "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN_PRIVATE_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_HOME_PRIVATE}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" == "0" ] && [ "$(curl "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN_PRIVATE_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_DATA_PUBLIC}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" == "0" ] && [ "$(curl "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN_PRIVATE_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_DATA_PRIVATE}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" == "0" ] && [ "$(curl "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN_PRIVATE_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_HOST_PRIVATE}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" == "0" ]
then
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "The service [influxdb] is ready :)" >&2
  exit 0
else
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "The service [influxdb] is *NOT* ready :(" >&2
  exit 1
fi
