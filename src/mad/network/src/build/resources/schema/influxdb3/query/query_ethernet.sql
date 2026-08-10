--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- ethernet/port [switch port health, one row per monitored port] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time)               AS "Bucket",
    port                                           AS "Port",
    round(avg(up), 1)                              AS "Up Fraction",
    round(last_value(speed_mbps ORDER BY time), 1) AS "Speed Mbps",
    round(avg(full_duplex), 1)                     AS "Full Duplex Fraction",
    round(avg(degraded), 1)                        AS "Degraded Fraction",
    round(last_value(errors ORDER BY time), 1)     AS "Errors"
FROM ethernet
WHERE
    port IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM ethernet) - INTERVAL '1 day'
GROUP BY "Bucket", port
ORDER BY "Bucket", port;
