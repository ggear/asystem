--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- light [Home Assistant light] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time)         AS "Bucket",
    entity_id                                AS "Entity Id",
    round(avg(brightness), 1)                AS "Brightness",
    last_value(brightness_str ORDER BY time) AS "Brightness Str",
    last_value(effect_str ORDER BY time)     AS "Effect Str",
    last_value(state ORDER BY time)          AS "State",
    round(avg(value), 1)                     AS "Value"
FROM light
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM light) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
