#!/usr/bin/env bash
################################################################################
# WARNING: This file is written by the build process, any manual edits will be lost!
################################################################################

POSITIONAL_ARGS=()
HEALTHCHECK_VERBOSE=${HEALTHCHECK_VERBOSE:-false}
while [[ $# -gt 0 ]]; do
  case $1 in
  -v | --verbose)
    HEALTHCHECK_VERBOSE=true
    POSITIONAL_ARGS+=("$1")
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

if [ "${HEALTHCHECK_VERBOSE}" == true ]; then
  alias curl="curl -f --connect-timeout 2 --max-time 2"
  set -x
else
  alias curl="curl -sf --connect-timeout 2 --max-time 2"
fi

shopt -s expand_aliases

if
  /asystem/etc/checkexecuting.sh "${POSITIONAL_ARGS[@]}" && [ "$(influx ping --host http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT})" == "OK" ] && influx query 'from(bucket:"'"${INFLUXDB_BUCKET_HOME_PUBLIC}"'") |> range(start:-15m) |> filter(fn: (r) => r["_measurement"] == "a_non_existent_metric")' && influx query 'from(bucket:"'"${INFLUXDB_BUCKET_HOME_PRIVATE}"'") |> range(start:-15m) |> filter(fn: (r) => r["_measurement"] == "a_non_existent_metric")' && influx query 'from(bucket:"'"${INFLUXDB_BUCKET_DATA_PUBLIC}"'") |> range(start:-15m) |> filter(fn: (r) => r["_measurement"] == "a_non_existent_metric")' && influx query 'from(bucket:"'"${INFLUXDB_BUCKET_DATA_PRIVATE}"'") |> range(start:-15m) |> filter(fn: (r) => r["_measurement"] == "a_non_existent_metric")' && influx query 'from(bucket:"'"${INFLUXDB_BUCKET_HOST_PRIVATE}"'") |> range(start:-15m) |> filter(fn: (r) => r["_measurement"] == "a_non_existent_metric")' && [ "$(curl "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PUBLIC}:${INFLUXDB_TOKEN_PUBLIC_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_HOME_PUBLIC}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" == "0" ] && [ "$(curl "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PUBLIC}:${INFLUXDB_TOKEN_PUBLIC_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_DATA_PUBLIC}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" == "0" ] && [ "$(curl "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN_PRIVATE_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_HOME_PUBLIC}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" == "0" ] && [ "$(curl "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN_PRIVATE_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_HOME_PRIVATE}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" == "0" ] && [ "$(curl "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN_PRIVATE_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_DATA_PUBLIC}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" == "0" ] && [ "$(curl "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN_PRIVATE_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_DATA_PRIVATE}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" == "0" ] && [ "$(curl "http://${INFLUXDB_SERVICE}:${INFLUXDB_HTTP_PORT}/query" --user "${INFLUXDB_USER_PRIVATE}:${INFLUXDB_TOKEN_PRIVATE_V1}" --data-urlencode "db=${INFLUXDB_BUCKET_HOST_PRIVATE}" --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" | jq -er .results[0].statement_id)" == "0" ]
then
  set +x
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "✅ The service [influxdb] is healthy :)" >&2
  exit 0
else
  set +x
  [ "${HEALTHCHECK_VERBOSE}" == true ] && echo "❌ The service [influxdb] is *NOT* healthy :(" >&2
  exit 1
fi
