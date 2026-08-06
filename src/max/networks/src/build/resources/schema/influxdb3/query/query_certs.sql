--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- certs/home [certificate health across the monitored endpoints] every 15m
SELECT
    date_bin(INTERVAL '1 hour', time)          AS bucket,
    avg(ok)                                    AS ok_fraction,
    last_value(score ORDER BY time)            AS score,
    avg(min_expiry_days)                       AS min_expiry_days_avg,
    min(min_expiry_days)                       AS min_expiry_days_min,
    max(min_expiry_days)                       AS min_expiry_days_max,
    last_value(endpoints_total ORDER BY time)  AS endpoints_total,
    last_value(endpoints_failed ORDER BY time) AS endpoints_failed
FROM certs
WHERE
    time > now() - INTERVAL '7 days'
GROUP BY bucket
ORDER BY bucket;
