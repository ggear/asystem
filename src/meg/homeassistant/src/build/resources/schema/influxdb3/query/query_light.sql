--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- light [Home Assistant light] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time)     AS "Bucket",
    entity_id                            AS "Entity Id",
    round(avg(assumed_state), 1)         AS "Assumed State",
    round(avg(brightness), 1)            AS "Brightness",
    round(avg(max_color_temp_kelvin), 1) AS "Max Color Temp Kelvin",
    round(avg(min_color_temp_kelvin), 1) AS "Min Color Temp Kelvin",
    round(avg(rgb_color), 1)             AS "Rgb Color",
    round(avg(value), 1)                 AS "Value"
FROM light
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM light) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
