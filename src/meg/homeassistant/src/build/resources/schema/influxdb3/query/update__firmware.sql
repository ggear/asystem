--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- update__firmware [Home Assistant update__firmware] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 3:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(installed_version), 1)                         AS "Installed Version Avg",
    round(min(installed_version), 1)                         AS "Installed Version Min",
    round(max(installed_version), 1)                         AS "Installed Version Max",
    count(installed_version)                                 AS "Installed Version Count",
    count(DISTINCT installed_version)                        AS "Installed Version Distinct"
FROM update__firmware
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM update__firmware) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- update__firmware [Home Assistant update__firmware] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 2 of 3:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(latest_version), 1)                            AS "Latest Version Avg",
    round(min(latest_version), 1)                            AS "Latest Version Min",
    round(max(latest_version), 1)                            AS "Latest Version Max",
    count(latest_version)                                    AS "Latest Version Count",
    count(DISTINCT latest_version)                           AS "Latest Version Distinct",
    last_value(state ORDER BY time)                          AS "State",
    count(state)                                             AS "State Count",
    count(DISTINCT state)                                    AS "State Distinct"
FROM update__firmware
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM update__firmware) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- update__firmware [Home Assistant update__firmware] every <on-change>, bucketed [1 day] across the newest two buckets
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
FROM update__firmware
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM update__firmware) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
