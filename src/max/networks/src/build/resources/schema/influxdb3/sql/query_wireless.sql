--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- wireless/wifi [access point health across the wireless estate] every 15m
SELECT
    date_bin(INTERVAL '1 hour', time)   AS bucket,
    avg(ok)                             AS ok_fraction,
    last_value(score ORDER BY time)     AS score,
    last_value(aps_total ORDER BY time) AS aps_total,
    last_value(aps_ok ORDER BY time)    AS aps_ok,
    avg(avg_experience_pct)             AS avg_experience_pct_avg,
    min(avg_experience_pct)             AS avg_experience_pct_min,
    max(avg_experience_pct)             AS avg_experience_pct_max
FROM wireless
WHERE
    time > now() - INTERVAL '7 days'
GROUP BY bucket
ORDER BY bucket;
