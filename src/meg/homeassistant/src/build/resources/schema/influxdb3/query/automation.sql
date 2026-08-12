--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- automation [Home Assistant automation] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time)             AS "Bucket",
    entity_id                                    AS "Entity Id",
    round(avg(last_triggered), 1)                AS "Last Triggered",
    last_value(last_triggered_str ORDER BY time) AS "Last Triggered Str",
    last_value(state ORDER BY time)              AS "State",
    round(avg(value), 1)                         AS "Value"
FROM automation
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM automation) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
