--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- sensor__atmospheric_pressure [Home Assistant sensor__atmospheric_pressure] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    unit_of_measurement              AS "Unit Of Measurement",
    round(avg(latitude), 1)          AS "Latitude",
    round(avg(longitude), 1)         AS "Longitude",
    round(avg(value), 1)             AS "Value"
FROM sensor__atmospheric_pressure
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor__atmospheric_pressure) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;
