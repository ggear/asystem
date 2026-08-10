--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- automation [Home Assistant automation] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(avg(last_triggered), 1)    AS "Last Triggered Avg",
    round(min(last_triggered), 1)    AS "Last Triggered Min",
    round(max(last_triggered), 1)    AS "Last Triggered Max",
    round(avg(max), 1)               AS "Max Avg",
    round(min(max), 1)               AS "Max Min",
    round(max(max), 1)               AS "Max Max",
    round(avg(value), 1)             AS "Value Avg",
    round(min(value), 1)             AS "Value Min",
    round(max(value), 1)             AS "Value Max"
FROM automation
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM automation) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
