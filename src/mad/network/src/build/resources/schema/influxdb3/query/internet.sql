--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- internet/target [internet reachability, one row per ping target] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    target                           AS "Target",
    round(avg(reachable), 1)         AS "Reachable Fraction",
    round(avg(loss_pct), 1)          AS "Loss Pct Avg",
    round(min(loss_pct), 1)          AS "Loss Pct Min",
    round(max(loss_pct), 1)          AS "Loss Pct Max",
    round(avg(rtt_ms), 1)            AS "Rtt Ms Avg",
    round(min(rtt_ms), 1)            AS "Rtt Ms Min",
    round(max(rtt_ms), 1)            AS "Rtt Ms Max",
    round(avg(jitter_ms), 1)         AS "Jitter Ms Avg",
    round(min(jitter_ms), 1)         AS "Jitter Ms Min",
    round(max(jitter_ms), 1)         AS "Jitter Ms Max"
FROM internet
WHERE
    module = 'network'
    AND target IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM internet) - INTERVAL '1 day'
GROUP BY "Bucket", target
ORDER BY "Bucket", target;
