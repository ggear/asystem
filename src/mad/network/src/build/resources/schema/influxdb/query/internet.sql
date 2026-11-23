--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- internet/target [internet reachability, one row per ping target] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 2:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    target                                                   AS "Target",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(reachable), 1)                                 AS "Reachable Fraction",
    count(reachable)                                         AS "Reachable Count",
    count(DISTINCT reachable)                                AS "Reachable Distinct",
    round(avg(loss_pct), 1)                                  AS "Loss Pct Avg",
    round(min(loss_pct), 1)                                  AS "Loss Pct Min",
    round(max(loss_pct), 1)                                  AS "Loss Pct Max",
    count(loss_pct)                                          AS "Loss Pct Count",
    count(DISTINCT loss_pct)                                 AS "Loss Pct Distinct"
FROM internet
WHERE
    module = 'network'
    AND target IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM internet) - INTERVAL '1 day'
GROUP BY "Bucket", target
ORDER BY "Bucket", target;

-- internet/target [internet reachability, one row per ping target] every 15m, bucketed [1 day] across the newest two buckets
-- part 2 of 2:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    target                                                   AS "Target",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(rtt_ms), 1)                                    AS "Rtt Ms Avg",
    round(min(rtt_ms), 1)                                    AS "Rtt Ms Min",
    round(max(rtt_ms), 1)                                    AS "Rtt Ms Max",
    count(rtt_ms)                                            AS "Rtt Ms Count",
    count(DISTINCT rtt_ms)                                   AS "Rtt Ms Distinct",
    round(avg(jitter_ms), 1)                                 AS "Jitter Ms Avg",
    round(min(jitter_ms), 1)                                 AS "Jitter Ms Min",
    round(max(jitter_ms), 1)                                 AS "Jitter Ms Max",
    count(jitter_ms)                                         AS "Jitter Ms Count",
    count(DISTINCT jitter_ms)                                AS "Jitter Ms Distinct"
FROM internet
WHERE
    module = 'network'
    AND target IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM internet) - INTERVAL '1 day'
GROUP BY "Bucket", target
ORDER BY "Bucket", target;
