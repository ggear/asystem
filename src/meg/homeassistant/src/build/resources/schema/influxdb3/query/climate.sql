--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- climate [Home Assistant climate] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time)          AS "Bucket",
    entity_id                                 AS "Entity Id",
    round(avg(current_temperature), 1)        AS "Current Temperature",
    last_value(hvac_action_str ORDER BY time) AS "Hvac Action Str",
    last_value(state ORDER BY time)           AS "State",
    round(avg(temperature), 1)                AS "Temperature"
FROM climate
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM climate) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
