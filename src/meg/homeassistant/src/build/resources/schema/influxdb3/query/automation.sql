--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- automation [Home Assistant automation] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 3:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(last_triggered), 1)                            AS "Last Triggered Avg",
    round(min(last_triggered), 1)                            AS "Last Triggered Min",
    round(max(last_triggered), 1)                            AS "Last Triggered Max",
    count(last_triggered)                                    AS "Last Triggered Count",
    count(DISTINCT last_triggered)                           AS "Last Triggered Distinct"
FROM automation
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM automation) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- automation [Home Assistant automation] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 2 of 3:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    last_value(last_triggered_str ORDER BY time)             AS "Last Triggered Str",
    count(last_triggered_str)                                AS "Last Triggered Str Count",
    count(DISTINCT last_triggered_str)                       AS "Last Triggered Str Distinct",
    last_value(state ORDER BY time)                          AS "State",
    count(state)                                             AS "State Count",
    count(DISTINCT state)                                    AS "State Distinct"
FROM automation
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM automation) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- automation [Home Assistant automation] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 3 of 3:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(value), 1)                                     AS "Value Avg",
    round(min(value), 1)                                     AS "Value Min",
    round(max(value), 1)                                     AS "Value Max",
    count(value)                                             AS "Value Count",
    count(DISTINCT value)                                    AS "Value Distinct"
FROM automation
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM automation) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
