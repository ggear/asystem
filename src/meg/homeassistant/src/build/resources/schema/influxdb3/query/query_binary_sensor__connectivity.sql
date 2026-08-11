--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- binary_sensor__connectivity [Home Assistant binary_sensor__connectivity] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(avg(latitude), 1)          AS "Latitude",
    round(avg(longitude), 1)         AS "Longitude",
    round(avg(value), 1)             AS "Value"
FROM binary_sensor__connectivity
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM binary_sensor__connectivity) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
