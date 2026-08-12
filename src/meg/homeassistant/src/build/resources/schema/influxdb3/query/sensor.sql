--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time)         AS "Bucket",
    entity_id                                AS "Entity Id",
    unit_of_measurement                      AS "Unit Of Measurement",
    round(avg(last_reset), 1)                AS "Last Reset",
    last_value(last_reset_str ORDER BY time) AS "Last Reset Str",
    round(avg(next_reset), 1)                AS "Next Reset",
    last_value(next_reset_str ORDER BY time) AS "Next Reset Str",
    last_value(state ORDER BY time)          AS "State",
    round(avg(value), 1)                     AS "Value",
    last_value(warnings_str ORDER BY time)   AS "Warnings Str"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;
