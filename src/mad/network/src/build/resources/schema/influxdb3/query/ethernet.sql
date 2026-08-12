--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- ethernet/port [switch port health, one row per monitored port] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 2:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    port                                                     AS "Port",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(up), 1)                                        AS "Up Fraction",
    count(up)                                                AS "Up Count",
    count(DISTINCT up)                                       AS "Up Distinct",
    round(last_value(speed_mbps ORDER BY time), 1)           AS "Speed Mbps",
    count(speed_mbps)                                        AS "Speed Mbps Count",
    count(DISTINCT speed_mbps)                               AS "Speed Mbps Distinct",
    round(avg(full_duplex), 1)                               AS "Full Duplex Fraction",
    count(full_duplex)                                       AS "Full Duplex Count",
    count(DISTINCT full_duplex)                              AS "Full Duplex Distinct"
FROM ethernet
WHERE
    module = 'network'
    AND port IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM ethernet) - INTERVAL '1 day'
GROUP BY "Bucket", port
ORDER BY "Bucket", port;

-- ethernet/port [switch port health, one row per monitored port] every 15m, bucketed [1 day] across the newest two buckets
-- part 2 of 2:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    port                                                     AS "Port",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(degraded), 1)                                  AS "Degraded Fraction",
    count(degraded)                                          AS "Degraded Count",
    count(DISTINCT degraded)                                 AS "Degraded Distinct",
    round(last_value(errors ORDER BY time), 1)               AS "Errors",
    count(errors)                                            AS "Errors Count",
    count(DISTINCT errors)                                   AS "Errors Distinct"
FROM ethernet
WHERE
    module = 'network'
    AND port IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM ethernet) - INTERVAL '1 day'
GROUP BY "Bucket", port
ORDER BY "Bucket", port;
