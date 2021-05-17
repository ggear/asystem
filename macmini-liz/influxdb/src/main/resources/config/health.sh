#!/bin/sh

. /root/.influxdbv2/.profile

apt-get install -y jq=1.5+dfsg-2+b1 curl=7.64.0-4+deb10u2 expect=5.45.4-2 netcat=1.10-41.1

set -e

influx ping --host http://${INFLUXDB_HOST}:${INFLUXDB_PORT}

curl --get http://localhost:8086/query \
  --user "${INFLUXDB_USER_ALL}:${INFLUXDB_TOKEN}" \
  --data-urlencode "db=${INFLUXDB_BUCKET_HOME_PUBLIC}" \
  --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" \
  && echo ""
curl --get http://localhost:8086/query \
  --user "${INFLUXDB_USER_ALL}:${INFLUXDB_TOKEN}" \
  --data-urlencode "db=${INFLUXDB_BUCKET_HOME_PRIVATE}" \
  --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" \
  && echo ""
curl --get http://localhost:8086/query \
  --user "${INFLUXDB_USER_ALL}:${INFLUXDB_TOKEN}" \
  --data-urlencode "db=${INFLUXDB_BUCKET_HOST_PRIVATE}" \
  --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" \
  && echo ""

curl --get http://localhost:8086/query \
  --user "${INFLUXDB_USER_PUBLIC}:${INFLUXDB_TOKEN_PUBLIC_V1}" \
  --data-urlencode "db=${INFLUXDB_BUCKET_HOME_PUBLIC}" \
  --data-urlencode "q=SELECT count(*) FROM a_non_existent_metric WHERE time >= now() - 15m" \
  && echo ""
