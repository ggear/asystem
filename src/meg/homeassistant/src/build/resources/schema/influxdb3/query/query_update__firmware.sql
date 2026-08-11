--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- update__firmware [Home Assistant update__firmware] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 3:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(avg(auto_update), 1)       AS "Auto Update Avg",
    round(min(auto_update), 1)       AS "Auto Update Min",
    round(max(auto_update), 1)       AS "Auto Update Max",
    round(avg(display_precision), 1) AS "Display Precision Avg",
    round(min(display_precision), 1) AS "Display Precision Min",
    round(max(display_precision), 1) AS "Display Precision Max",
    round(avg(in_progress), 1)       AS "In Progress Avg"
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
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(min(in_progress), 1)       AS "In Progress Min",
    round(max(in_progress), 1)       AS "In Progress Max",
    round(avg(installed_version), 1) AS "Installed Version Avg",
    round(min(installed_version), 1) AS "Installed Version Min",
    round(max(installed_version), 1) AS "Installed Version Max",
    round(avg(latest_version), 1)    AS "Latest Version Avg",
    round(min(latest_version), 1)    AS "Latest Version Min"
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
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(max(latest_version), 1)    AS "Latest Version Max",
    round(avg(update_percentage), 1) AS "Update Percentage Avg",
    round(min(update_percentage), 1) AS "Update Percentage Min",
    round(max(update_percentage), 1) AS "Update Percentage Max",
    round(avg(value), 1)             AS "Value Avg",
    round(min(value), 1)             AS "Value Min",
    round(max(value), 1)             AS "Value Max"
FROM update__firmware
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM update__firmware) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
