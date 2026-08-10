--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- switch [Home Assistant switch] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 3:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(avg(assumed_state), 1)     AS "Assumed State Avg",
    round(min(assumed_state), 1)     AS "Assumed State Min",
    round(max(assumed_state), 1)     AS "Assumed State Max",
    round(avg(brightness_pct), 1)    AS "Brightness Pct Avg",
    round(min(brightness_pct), 1)    AS "Brightness Pct Min",
    round(max(brightness_pct), 1)    AS "Brightness Pct Max",
    round(avg(force_rgb_color), 1)   AS "Force Rgb Color Avg"
FROM switch
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM switch) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- switch [Home Assistant switch] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 2 of 3:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(min(force_rgb_color), 1)   AS "Force Rgb Color Min",
    round(max(force_rgb_color), 1)   AS "Force Rgb Color Max",
    round(avg(rgb_color), 1)         AS "Rgb Color Avg",
    round(min(rgb_color), 1)         AS "Rgb Color Min",
    round(max(rgb_color), 1)         AS "Rgb Color Max",
    round(avg(sun_position), 1)      AS "Sun Position Avg",
    round(min(sun_position), 1)      AS "Sun Position Min",
    round(max(sun_position), 1)      AS "Sun Position Max"
FROM switch
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM switch) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- switch [Home Assistant switch] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 3 of 3:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(avg(value), 1)             AS "Value Avg",
    round(min(value), 1)             AS "Value Min",
    round(max(value), 1)             AS "Value Max"
FROM switch
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM switch) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
