#!/bin/bash

influxdb3 show databases

influxdb3 query \
  --database host_private \
  "SHOW TABLES"

influxdb3 query \
  --language influxql \
  --database host_private \
  "SHOW TAG KEYS FROM cpu"

influxdb3 query \
  --language influxql \
  --database host_private \
  "SHOW FIELD KEYS FROM cpu"

influxdb3 query \
  --language influxql \
  --database host_private \
  "SHOW TAG VALUES FROM cpu WITH KEY = host"

influxdb3 query \
  --language influxql \
  --format json \
  --database host_private \
  "SELECT COUNT(usage_system) FROM cpu" | jq -r '.[0].count'

influxdb3 query \
  --language influxql \
  --database host_private "
    SELECT
      time, host, usage_system, usage_user
    FROM cpu
    GROUP BY host
    ORDER BY time DESC
    LIMIT 1
"

influxdb3 query \
  --language influxql \
  --database host_private "
    SELECT
      time, host, usage_system, usage_user
    FROM cpu
    WHERE
      time >= now() - 10s
    ORDER by time DESC
"

influxdb3 query \
  --language influxql \
  --database host_private "
    SELECT MEAN(usage_system) AS max_usage_system,
           MEAN(usage_user) AS max_usage_user
    FROM cpu
    WHERE usage_system != 0 AND usage_user != 0
    GROUP BY time(24h, 8h), host
    ORDER BY time DESC
"
