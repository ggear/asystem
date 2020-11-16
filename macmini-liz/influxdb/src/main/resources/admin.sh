#!/bin/sh

. config/.profile

#influx config create \
#    --config-name influx_old \
#    --host-url http://macmini-liz:9999 \
#    --org home \
#    --token ${INFLUXDB_TOKEN}
#
#influx config create \
#    --config-name influx_new \
#    --host-url http://macmini-liz:8086 \
#    --org home \
#    --token ${INFLUXDB_TOKEN}
#
#influx export all -c influx_old | influx apply -c influx_new
#
#influx query -c influx_old 'from(bucket: "asystem") |> range(start: -3y)' --raw > /tmp/data.csv
#influx query -c influx_new 'from(bucket: "asystem") |> range(start: -1m)' --raw > /tmp/asystem_$(date +%s).csv
#
#influx write -c influx_new --format csv -b asystem -f /tmp/data.csv --skipRowOnError

ORG_ID="e20dcc436a89fa52"
ORG_NAME="home"
BUCKET_ID_HOSTS="2de730f52b92fae0"
BUCKET_ID_ASYSTEM="d7c9c0c45bcf09ff"

set -x

curl -G --silent --request GET http://macmini-liz:8086/api/v2/authorizations \
  --header "Authorization: Token ${INFLUXDB_TOKEN}" \
  --header "Content-type: application/json" \
  --data-urlencode "org=${ORG_NAME}"

curl -G --silent --request GET http://macmini-liz:8086/api/v2/buckets \
  --header "Authorization: Token ${INFLUXDB_TOKEN}" \
  --header "Content-type: application/json" \
  --data-urlencode "org=${ORG_NAME}"

curl --silent --request POST http://macmini-liz:8086/api/v2/dbrps \
  --header "Authorization: Token ${INFLUXDB_TOKEN}" \
  --header 'Content-type: application/json' \
  --data '{
    "organization_id": "'${ORG_ID}'",
    "bucket_id": "'${BUCKET_ID_HOSTS}'",
    "database": "asystem",
    "retention_policy": "autogen",
    "default": true
  }'

curl --silent --request POST http://macmini-liz:8086/api/v2/dbrps \
  --header "Authorization: Token ${INFLUXDB_TOKEN}" \
  --header 'Content-type: application/json' \
  --data '{
    "organization_id": "'${ORG_ID}'",
    "bucket_id": "'${BUCKET_ID_ASYSTEM}'",
    "database": "hosts",
    "retention_policy": "autogen",
    "default": true
  }'

curl -G --silent --request GET http://macmini-liz:8086/api/v2/dbrps \
  --header "Authorization: Token ${INFLUXDB_TOKEN}" \
  --header "Content-type: application/json" \
  --data-urlencode "orgID=${ORG_ID}"

curl --silent -POST 'http://macmini-liz:8086/write?db=hosts' \
  --header "Authorization: Token ${INFLUXDB_TOKEN}" \
  --data-raw 'test_metric,test_tag=test_tag_value test_value=0'

curl --silent -POST 'http://macmini-liz:8086/write?db=asystem' \
  --header "Authorization: Token ${INFLUXDB_TOKEN}" \
  --data-raw 'test_metric,test_tag=test_tag_value test_value=0'

curl -G --silent --request GET http://macmini-liz:8086/query \
  --header "Authorization: Token ${INFLUXDB_TOKEN}" \
  --data-urlencode "db=asystem" \
  --data-urlencode "q=SELECT count(*) FROM test_metric WHERE time >= now() - 15m"

curl -G --silent --request GET http://influxdb:${INFLUXDB_TOKEN}@macmini-liz:8086/query \
  --data-urlencode "db=hosts" \
  --data-urlencode "q=SELECT count(*) FROM test_metric WHERE time >= now() - 15m"

echo "" && echo ""
