--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- device_tracker [Home Assistant device_tracker] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(avg(altitude), 1)          AS "Altitude",
    round(avg(battery_level), 1)     AS "Battery Level",
    round(avg(gps_accuracy), 1)      AS "Gps Accuracy",
    round(avg(latitude), 1)          AS "Latitude",
    round(avg(longitude), 1)         AS "Longitude",
    round(avg(value), 1)             AS "Value",
    round(avg(vertical_accuracy), 1) AS "Vertical Accuracy"
FROM device_tracker
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM device_tracker) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
