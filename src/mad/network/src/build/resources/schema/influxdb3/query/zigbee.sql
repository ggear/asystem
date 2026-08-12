--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- zigbee/device [mesh device state reported by the coordinator, one row per paired device] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 2:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    device                                                   AS "Device",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(available), 1)                                 AS "Available Fraction",
    count(available)                                         AS "Available Count",
    count(DISTINCT available)                                AS "Available Distinct",
    round(avg(coordinator), 1)                               AS "Coordinator Fraction",
    count(coordinator)                                       AS "Coordinator Count",
    count(DISTINCT coordinator)                              AS "Coordinator Distinct",
    round(last_value(lqi ORDER BY time), 1)                  AS "Lqi",
    count(lqi)                                               AS "Lqi Count",
    count(DISTINCT lqi)                                      AS "Lqi Distinct"
FROM zigbee
WHERE
    module = 'network'
    AND device IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM zigbee) - INTERVAL '1 day'
GROUP BY "Bucket", device
ORDER BY "Bucket", device;

-- zigbee/device [mesh device state reported by the coordinator, one row per paired device] every 15m, bucketed [1 day] across the newest two buckets
-- part 2 of 2:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    device                                                   AS "Device",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(weak), 1)                                      AS "Weak Fraction",
    count(weak)                                              AS "Weak Count",
    count(DISTINCT weak)                                     AS "Weak Distinct"
FROM zigbee
WHERE
    module = 'network'
    AND device IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM zigbee) - INTERVAL '1 day'
GROUP BY "Bucket", device
ORDER BY "Bucket", device;
