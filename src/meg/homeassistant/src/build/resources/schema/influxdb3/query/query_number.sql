--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- number [Home Assistant number] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    unit_of_measurement              AS "Unit Of Measurement",
    round(avg(max), 1)               AS "Max Avg",
    round(min(max), 1)               AS "Max Min",
    round(max(max), 1)               AS "Max Max",
    round(avg(min), 1)               AS "Min Avg",
    round(min(min), 1)               AS "Min Min",
    round(max(min), 1)               AS "Min Max",
    round(avg(step), 1)              AS "Step Avg",
    round(min(step), 1)              AS "Step Min",
    round(max(step), 1)              AS "Step Max",
    round(avg(value), 1)             AS "Value Avg",
    round(min(value), 1)             AS "Value Min",
    round(max(value), 1)             AS "Value Max"
FROM number
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM number) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;
