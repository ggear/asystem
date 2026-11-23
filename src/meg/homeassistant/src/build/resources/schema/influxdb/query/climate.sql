--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- climate [Home Assistant climate] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 3:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(current_temperature), 1)                       AS "Current Temperature Avg",
    round(min(current_temperature), 1)                       AS "Current Temperature Min",
    round(max(current_temperature), 1)                       AS "Current Temperature Max",
    count(current_temperature)                               AS "Current Temperature Count",
    count(DISTINCT current_temperature)                      AS "Current Temperature Distinct"
FROM climate
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM climate) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- climate [Home Assistant climate] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 2 of 3:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    last_value(hvac_action_str ORDER BY time)                AS "Hvac Action Str",
    count(hvac_action_str)                                   AS "Hvac Action Str Count",
    count(DISTINCT hvac_action_str)                          AS "Hvac Action Str Distinct",
    last_value(state ORDER BY time)                          AS "State",
    count(state)                                             AS "State Count",
    count(DISTINCT state)                                    AS "State Distinct"
FROM climate
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM climate) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- climate [Home Assistant climate] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 3 of 3:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(temperature), 1)                               AS "Temperature Avg",
    round(min(temperature), 1)                               AS "Temperature Min",
    round(max(temperature), 1)                               AS "Temperature Max",
    count(temperature)                                       AS "Temperature Count",
    count(DISTINCT temperature)                              AS "Temperature Distinct"
FROM climate
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM climate) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
