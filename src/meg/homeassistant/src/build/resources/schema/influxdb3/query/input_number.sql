--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- input_number [Home Assistant input_number] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    unit_of_measurement                                      AS "Unit Of Measurement",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    last_value(initial_str ORDER BY time)                    AS "Initial Str",
    count(initial_str)                                       AS "Initial Str Count",
    count(DISTINCT initial_str)                              AS "Initial Str Distinct",
    round(avg(value), 1)                                     AS "Value Avg",
    round(min(value), 1)                                     AS "Value Min",
    round(max(value), 1)                                     AS "Value Max",
    count(value)                                             AS "Value Count",
    count(DISTINCT value)                                    AS "Value Distinct"
FROM input_number
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM input_number) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;
