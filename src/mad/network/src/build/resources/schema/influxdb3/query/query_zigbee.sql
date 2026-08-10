--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- zigbee/device [mesh device state reported by the coordinator, one row per paired device] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time)        AS "Bucket",
    device                                  AS "Device",
    round(avg(available), 1)                AS "Available Fraction",
    round(avg(coordinator), 1)              AS "Coordinator Fraction",
    round(last_value(lqi ORDER BY time), 1) AS "Lqi",
    round(avg(weak), 1)                     AS "Weak Fraction"
FROM zigbee
WHERE
    device IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM zigbee) - INTERVAL '1 day'
GROUP BY "Bucket", device
ORDER BY "Bucket", device;
