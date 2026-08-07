--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- tempstat/device [the tempstat service itself, one row set per poll] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    time_bucket('1 day', time)                                                    AS "Bucket",
    entity                                                                        AS "Device",
    round((last(value, time) FILTER (WHERE type = 'period_ms'))::numeric, 1)      AS "Period Ms",
    round((last(value, time) FILTER (WHERE type = 'sensors_failed'))::numeric, 1) AS "Sensors Failed"
FROM tempstat
WHERE
    type IN ('period_ms', 'sensors_failed')
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM tempstat) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;

-- tempstat/sensor [one DS18B20 probe on the one-wire bus] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    time_bucket('1 day', time)                                                  AS "Bucket",
    entity                                                                      AS "Sensor",
    round((avg(value) FILTER (WHERE type = 'temperature_celsius'))::numeric, 1) AS "Temperature Celsius Avg",
    round((min(value) FILTER (WHERE type = 'temperature_celsius'))::numeric, 1) AS "Temperature Celsius Min",
    round((max(value) FILTER (WHERE type = 'temperature_celsius'))::numeric, 1) AS "Temperature Celsius Max"
FROM tempstat
WHERE
    type IN ('temperature_celsius')
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM tempstat) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;
