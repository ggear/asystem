--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- internet/gateway [internet reachability through the local gateway and the public ping targets] every 15m
SELECT
    date_bin(INTERVAL '1 hour', time)       AS bucket,
    avg(ok)                                 AS ok_fraction,
    last_value(score ORDER BY time)         AS score,
    last_value(targets_total ORDER BY time) AS targets_total,
    last_value(targets_ok ORDER BY time)    AS targets_ok,
    avg(avg_loss_pct)                       AS avg_loss_pct_avg,
    min(avg_loss_pct)                       AS avg_loss_pct_min,
    max(avg_loss_pct)                       AS avg_loss_pct_max,
    avg(avg_rtt_ms)                         AS avg_rtt_ms_avg,
    min(avg_rtt_ms)                         AS avg_rtt_ms_min,
    max(avg_rtt_ms)                         AS avg_rtt_ms_max,
    avg(avg_jitter_ms)                      AS avg_jitter_ms_avg,
    min(avg_jitter_ms)                      AS avg_jitter_ms_min,
    max(avg_jitter_ms)                      AS avg_jitter_ms_max,
    avg(gateway_ok)                         AS gateway_ok_fraction
FROM internet
WHERE
    time > now() - INTERVAL '7 days'
GROUP BY bucket
ORDER BY bucket;
