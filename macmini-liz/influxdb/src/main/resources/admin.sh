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

set -x

curl -G --silent --request GET http://macmini-liz:8086/api/v2/authorizations \
  --header "Authorization: Token ${INFLUXDB_TOKEN}" \
  --header "Content-type: application/json" \
  --data-urlencode "orgID=3ac4477553d89245"

curl -G --silent --request GET http://macmini-liz:8086/api/v2/buckets \
  --header "Authorization: Token ${INFLUXDB_TOKEN}" \
  --header "Content-type: application/json" \
  --data-urlencode "orgID=3ac4477553d89245"

curl --silent --request POST http://macmini-liz:8086/api/v2/dbrps \
  --header "Authorization: Token ${INFLUXDB_TOKEN}" \
  --header 'Content-type: application/json' \
  --data '{
    "organization_id": "3ac4477553d89245",
    "bucket_id": "54b31e32e392a1cb",
    "database": "asystem",
    "retention_policy": "autogen",
    "default": true
  }'

curl --silent --request POST http://macmini-liz:8086/api/v2/dbrps \
  --header "Authorization: Token ${INFLUXDB_TOKEN}" \
  --header 'Content-type: application/json' \
  --data '{
    "organization_id": "3ac4477553d89245",
    "bucket_id": "fa47990c0ce24cd1",
    "database": "hosts",
    "retention_policy": "autogen",
    "default": true
  }'

curl -G --silent --request GET http://macmini-liz:8086/api/v2/dbrps \
  --header "Authorization: Token ${INFLUXDB_TOKEN}" \
  --header "Content-type: application/json" \
  --data-urlencode "orgID=3ac4477553d89245"

curl -G --silent --request GET http://macmini-liz:8086/query \
  --header "Authorization: Token ${INFLUXDB_TOKEN}" \
  --data-urlencode "db=asystem" \
  --data-urlencode "q=SELECT count(*) FROM W WHERE time >= now() - 15m"

curl -G --silent --request GET http://macmini-liz:8086/query \
  --header "Authorization: Token ${INFLUXDB_TOKEN}" \
  --data-urlencode "db=hosts" \
  --data-urlencode "q=SELECT count(*) FROM internet WHERE time >= now() - 15m"

curl --silent -POST 'http://macmini-liz:8086/write?db=hosts' \
  --header "Authorization: Token ${INFLUXDB_TOKEN}" \
  --data-raw 'test_measurement,test_tag=test_tag_value test_value=0'

curl --silent -POST 'http://macmini-liz:8086/write?db=asystem' \
  --header "Authorization: Token ${INFLUXDB_TOKEN}" \
  --data-raw 'test_measurement,test_tag=test_tag_value test_value=0'

curl --silent -POST 'http://macmini-liz:8086/write?db=hosts' \
  --header "Authorization: Token ${INFLUXDB_TOKEN}" \
  --data-binary 'test_measurement,test_tag=test_tag_value test_value=0'

echo "" && echo ""
