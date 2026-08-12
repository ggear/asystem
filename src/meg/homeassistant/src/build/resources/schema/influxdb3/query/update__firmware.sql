--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- update__firmware [Home Assistant update__firmware] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(avg(installed_version), 1) AS "Installed Version",
    round(avg(latest_version), 1)    AS "Latest Version",
    last_value(state ORDER BY time)  AS "State",
    round(avg(value), 1)             AS "Value"
FROM update__firmware
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM update__firmware) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
