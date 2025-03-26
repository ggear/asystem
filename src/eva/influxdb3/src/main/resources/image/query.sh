#!/bin/bash

influxdb3 show databases
influxdb3 query \
  --database host_private \
  "SHOW TABLES"
influxdb3 query \
  --language influxql \
  --database host_private \
  "SHOW MEASUREMENTS"
influxdb3 query \
  --language influxql \
  --database host_private \
  "SHOW FIELD KEYS FROM cpu"
influxdb3 query \
  --language influxql \
  --database host_private \
  "SHOW TAG KEYS FROM cpu"
influxdb3 query \
  --language influxql \
  --database host_private \
  "SHOW TAG VALUES FROM cpu WITH KEY = host"
influxdb3 query \
  --language influxql \
  --database host_private "
    SELECT
      time, host, usage_system, usage_user
    FROM cpu
    WHERE
      cpu = cpu-total AND
      time >= now() - 2h
--    time >= '2025-02-15T01:45:00Z' AND time <= '2025-02-15T01:45:30Z'
    ORDER by time DESC
    LIMIT 10
"
influxdb3 query \
  --language influxql \
  --format json \
  --database host_private \
  "SELECT COUNT(usage_system) FROM cpu" | jq -r '.[0].count'
