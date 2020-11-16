#!/bin/sh

. config/.profile

influx config create \
    --config-name influx_old \
    --host-url http://macmini-liz:9999 \
    --org home \
    --token ${INFLUXDB_TOKEN}

influx config create \
    --config-name influx_new \
    --host-url http://macmini-liz:8086 \
    --org home \
    --token ${INFLUXDB_TOKEN}

influx export all -c influx_old | influx apply -c influx_new

influx query -c influx_old 'from(bucket: "asystem") |> range(start: -3y)' --raw > /tmp/data.csv
influx query -c influx_new 'from(bucket: "asystem") |> range(start: -1m)' --raw > /tmp/asystem_$(date +%s).csv

influx write -c influx_new --format csv -b asystem -f /tmp/data.csv --skipRowOnError

curl -G --request GET http://macmini-liz:8086/api/v2/dbrps --header "Authorization: Token ${INFLUXDB_TOKEN}" --header "Content-type: application/json" --data-urlencode "org=home"

curl -G --request GET http://macmini-liz:8086/query --header "Authorization: Token ${INFLUXDB_TOKEN}" --data-urlencode "db=hosts" --data-urlencode "q=SELECT "uptime_s" FROM "internet" WHERE time >= now() - 15m"
