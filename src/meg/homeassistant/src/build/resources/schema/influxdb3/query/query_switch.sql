--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- switch [Home Assistant switch] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(avg(assumed_state), 1)     AS "Assumed State",
    round(avg(brightness_pct), 1)    AS "Brightness Pct",
    round(avg(force_rgb_color), 1)   AS "Force Rgb Color",
    round(avg(rgb_color), 1)         AS "Rgb Color",
    round(avg(sun_position), 1)      AS "Sun Position",
    round(avg(value), 1)             AS "Value"
FROM switch
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM switch) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
