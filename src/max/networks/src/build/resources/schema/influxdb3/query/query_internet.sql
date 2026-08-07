--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- internet/gateway [internet reachability through the local gateway and the public ping targets] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time)                  AS "Bucket",
    round(avg(ok), 1)                                 AS "Ok Fraction",
    round(last_value(score ORDER BY time), 1)         AS "Score",
    round(last_value(targets_total ORDER BY time), 1) AS "Targets Total",
    round(last_value(targets_ok ORDER BY time), 1)    AS "Targets Ok",
    round(avg(avg_loss_pct), 1)                       AS "Avg Loss Pct Avg",
    round(min(avg_loss_pct), 1)                       AS "Avg Loss Pct Min",
    round(max(avg_loss_pct), 1)                       AS "Avg Loss Pct Max",
    round(avg(avg_rtt_ms), 1)                         AS "Avg Rtt Ms Avg",
    round(min(avg_rtt_ms), 1)                         AS "Avg Rtt Ms Min",
    round(max(avg_rtt_ms), 1)                         AS "Avg Rtt Ms Max",
    round(avg(avg_jitter_ms), 1)                      AS "Avg Jitter Ms Avg",
    round(min(avg_jitter_ms), 1)                      AS "Avg Jitter Ms Min",
    round(max(avg_jitter_ms), 1)                      AS "Avg Jitter Ms Max",
    round(avg(gateway_ok), 1)                         AS "Gateway Ok Fraction"
FROM internet
WHERE
    time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM internet) - INTERVAL '1 day'
GROUP BY "Bucket"
ORDER BY "Bucket";
