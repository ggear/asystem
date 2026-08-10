--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- fan [Home Assistant fan] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(avg(assumed_state), 1)     AS "Assumed State Avg",
    round(min(assumed_state), 1)     AS "Assumed State Min",
    round(max(assumed_state), 1)     AS "Assumed State Max",
    round(avg(percentage), 1)        AS "Percentage Avg",
    round(min(percentage), 1)        AS "Percentage Min",
    round(max(percentage), 1)        AS "Percentage Max",
    round(avg(value), 1)             AS "Value Avg",
    round(min(value), 1)             AS "Value Min",
    round(max(value), 1)             AS "Value Max"
FROM fan
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM fan) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
