--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- zigbee/bridge [coordinator state and the mesh it reports] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time)                  AS "Bucket",
    round(avg(ok), 1)                                 AS "Ok Fraction",
    round(last_value(score ORDER BY time), 1)         AS "Score",
    round(last_value(devices_total ORDER BY time), 1) AS "Devices Total",
    round(last_value(devices_ok ORDER BY time), 1)    AS "Devices Ok",
    round(last_value(devices_weak ORDER BY time), 1)  AS "Devices Weak",
    round(avg(avg_lqi), 1)                            AS "Avg Lqi Avg",
    round(min(avg_lqi), 1)                            AS "Avg Lqi Min",
    round(max(avg_lqi), 1)                            AS "Avg Lqi Max"
FROM zigbee
WHERE
    time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM zigbee) - INTERVAL '1 day'
GROUP BY "Bucket"
ORDER BY "Bucket";
