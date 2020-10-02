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

influx write -c influx_new --format csv -b asystem -f /tmp/data.csv --skipRowOnError
