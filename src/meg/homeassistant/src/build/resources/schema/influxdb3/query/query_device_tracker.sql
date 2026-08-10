--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- device_tracker [Home Assistant device_tracker] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 3:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(avg(altitude), 1)          AS "Altitude Avg",
    round(min(altitude), 1)          AS "Altitude Min",
    round(max(altitude), 1)          AS "Altitude Max",
    round(avg(battery_level), 1)     AS "Battery Level Avg",
    round(min(battery_level), 1)     AS "Battery Level Min",
    round(max(battery_level), 1)     AS "Battery Level Max",
    round(avg(gps_accuracy), 1)      AS "Gps Accuracy Avg",
    round(min(gps_accuracy), 1)      AS "Gps Accuracy Min"
FROM device_tracker
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM device_tracker) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- device_tracker [Home Assistant device_tracker] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 2 of 3:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(max(gps_accuracy), 1)      AS "Gps Accuracy Max",
    round(avg(latitude), 1)          AS "Latitude Avg",
    round(min(latitude), 1)          AS "Latitude Min",
    round(max(latitude), 1)          AS "Latitude Max",
    round(avg(longitude), 1)         AS "Longitude Avg",
    round(min(longitude), 1)         AS "Longitude Min",
    round(max(longitude), 1)         AS "Longitude Max",
    round(avg(value), 1)             AS "Value Avg",
    round(min(value), 1)             AS "Value Min",
    round(max(value), 1)             AS "Value Max"
FROM device_tracker
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM device_tracker) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- device_tracker [Home Assistant device_tracker] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 3 of 3:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(avg(vertical_accuracy), 1) AS "Vertical Accuracy Avg",
    round(min(vertical_accuracy), 1) AS "Vertical Accuracy Min",
    round(max(vertical_accuracy), 1) AS "Vertical Accuracy Max"
FROM device_tracker
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM device_tracker) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
