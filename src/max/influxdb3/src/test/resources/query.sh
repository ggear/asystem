#!/bin/bash

influxdb3 show databases

influxdb3 query \
  --database host_private \
  "SHOW TABLES"

influxdb3 query \
  --language influxql \
  --database host_private \
  "SHOW TAG KEYS FROM supervisor"

influxdb3 query \
  --language influxql \
  --database host_private \
  "SHOW FIELD KEYS FROM supervisor"

influxdb3 query \
  --language influxql \
  --database host_private \
  "SHOW TAG VALUES FROM supervisor WITH KEY = host"

influxdb3 query \
  --language influxql \
  --format json \
  --database host_private \
  "SELECT COUNT(used_processor) FROM supervisor" | jq -r '.[0].count'

influxdb3 query \
  --language influxql \
  --database host_private "
    SELECT
      time, host, used_processor, used_processor_trend
    FROM supervisor
    GROUP BY host
    ORDER BY time DESC
    LIMIT 1
"

influxdb3 query \
  --language influxql \
  --database host_private "
    SELECT
      time, host, used_processor, used_processor_trend
    FROM supervisor
    WHERE
      time >= now() - 10s
    ORDER by time DESC
"

influxdb3 query \
  --language influxql \
  --database host_private "
    SELECT MEAN(used_processor) AS mean_used_processor,
           MEAN(used_processor_trend) AS mean_used_processor_trend
    FROM supervisor
    WHERE used_processor != 0 AND used_processor_trend != 0
    GROUP BY time(24h, 8h), host
    ORDER BY time DESC
"
