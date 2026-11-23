--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- sensor__voltage [Home Assistant sensor__voltage] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 3:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    unit_of_measurement                                      AS "Unit Of Measurement",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(buffer_usage_ratio), 1)                        AS "Buffer Usage Ratio Avg",
    round(min(buffer_usage_ratio), 1)                        AS "Buffer Usage Ratio Min",
    round(max(buffer_usage_ratio), 1)                        AS "Buffer Usage Ratio Max",
    count(buffer_usage_ratio)                                AS "Buffer Usage Ratio Count",
    count(DISTINCT buffer_usage_ratio)                       AS "Buffer Usage Ratio Distinct"
FROM sensor__voltage
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor__voltage) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor__voltage [Home Assistant sensor__voltage] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 2 of 3:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    unit_of_measurement                                      AS "Unit Of Measurement",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(source_value_valid), 1)                        AS "Source Value Valid Avg",
    round(min(source_value_valid), 1)                        AS "Source Value Valid Min",
    round(max(source_value_valid), 1)                        AS "Source Value Valid Max",
    count(source_value_valid)                                AS "Source Value Valid Count",
    count(DISTINCT source_value_valid)                       AS "Source Value Valid Distinct"
FROM sensor__voltage
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor__voltage) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor__voltage [Home Assistant sensor__voltage] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 3 of 3:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    unit_of_measurement                                      AS "Unit Of Measurement",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(value), 1)                                     AS "Value Avg",
    round(min(value), 1)                                     AS "Value Min",
    round(max(value), 1)                                     AS "Value Max",
    count(value)                                             AS "Value Count",
    count(DISTINCT value)                                    AS "Value Distinct"
FROM sensor__voltage
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor__voltage) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;
