--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- climate [Home Assistant climate] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 2:
SELECT
    date_bin(INTERVAL '1 day', time)   AS "Bucket",
    entity_id                          AS "Entity Id",
    round(avg(current_temperature), 1) AS "Current Temperature Avg",
    round(min(current_temperature), 1) AS "Current Temperature Min",
    round(max(current_temperature), 1) AS "Current Temperature Max",
    round(avg(max_temp), 1)            AS "Max Temp Avg",
    round(min(max_temp), 1)            AS "Max Temp Min",
    round(max(max_temp), 1)            AS "Max Temp Max",
    round(avg(min_temp), 1)            AS "Min Temp Avg",
    round(min(min_temp), 1)            AS "Min Temp Min"
FROM climate
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM climate) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- climate [Home Assistant climate] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 2 of 2:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(max(min_temp), 1)          AS "Min Temp Max",
    round(avg(temperature), 1)       AS "Temperature Avg",
    round(min(temperature), 1)       AS "Temperature Min",
    round(max(temperature), 1)       AS "Temperature Max"
FROM climate
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM climate) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
