--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- light [Home Assistant light] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 3:
SELECT
    date_bin(INTERVAL '1 day', time)     AS "Bucket",
    entity_id                            AS "Entity Id",
    round(avg(assumed_state), 1)         AS "Assumed State Avg",
    round(min(assumed_state), 1)         AS "Assumed State Min",
    round(max(assumed_state), 1)         AS "Assumed State Max",
    round(avg(brightness), 1)            AS "Brightness Avg",
    round(min(brightness), 1)            AS "Brightness Min",
    round(max(brightness), 1)            AS "Brightness Max",
    round(avg(max_color_temp_kelvin), 1) AS "Max Color Temp Kelvin Avg"
FROM light
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM light) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- light [Home Assistant light] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 2 of 3:
SELECT
    date_bin(INTERVAL '1 day', time)     AS "Bucket",
    entity_id                            AS "Entity Id",
    round(min(max_color_temp_kelvin), 1) AS "Max Color Temp Kelvin Min",
    round(max(max_color_temp_kelvin), 1) AS "Max Color Temp Kelvin Max",
    round(avg(min_color_temp_kelvin), 1) AS "Min Color Temp Kelvin Avg",
    round(min(min_color_temp_kelvin), 1) AS "Min Color Temp Kelvin Min",
    round(max(min_color_temp_kelvin), 1) AS "Min Color Temp Kelvin Max",
    round(avg(rgb_color), 1)             AS "Rgb Color Avg"
FROM light
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM light) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- light [Home Assistant light] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 3 of 3:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(min(rgb_color), 1)         AS "Rgb Color Min",
    round(max(rgb_color), 1)         AS "Rgb Color Max",
    round(avg(value), 1)             AS "Value Avg",
    round(min(value), 1)             AS "Value Min",
    round(max(value), 1)             AS "Value Max"
FROM light
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM light) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
