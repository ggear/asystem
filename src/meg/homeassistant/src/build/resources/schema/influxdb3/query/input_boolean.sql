--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- input_boolean [Home Assistant input_boolean] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    last_value(state ORDER BY time)                          AS "State",
    count(state)                                             AS "State Count",
    count(DISTINCT state)                                    AS "State Distinct",
    round(avg(value), 1)                                     AS "Value Avg",
    round(min(value), 1)                                     AS "Value Min",
    round(max(value), 1)                                     AS "Value Max",
    count(value)                                             AS "Value Count",
    count(DISTINCT value)                                    AS "Value Distinct"
FROM input_boolean
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM input_boolean) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
