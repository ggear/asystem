#!/bin/sh

influx config create \
    --config-name influx_old \
    --host-url http://macmini-liz:9999 \
    --org home \
    --token wMhIUIiC2UoceR5joo07AbjouNoN0jEjcNm-WihDvitV0i0M3u05uaVEAi-9C_2adHWZ903je3dpXR5ib4JjPA==

influx config create \
    --config-name influx_new \
    --host-url http://macmini-liz:8086 \
    --org home \
    --token aPh6OSxvyUXo6POASvvjjOJ1npgQ_lu0bZeUzOayI2WdPSauAIsXfc2hJpzc2OXXgoQavTWhCDx23KGUqJFskQ==

influx export all -c influx_old | influx apply -c influx_new

influx query -c influx_old 'from(bucket: "asystem") |> range(start: -3y)' --raw > /tmp/data.csv

influx write -c influx_new --format csv -b asystem -f /tmp/data.csv --skipRowOnError
