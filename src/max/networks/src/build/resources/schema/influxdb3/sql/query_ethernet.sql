--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- ethernet/ports [switch port health across the monitored ports] every 15m
SELECT
    date_bin(INTERVAL '1 hour', time)        AS bucket,
    last_value(score ORDER BY time)          AS score,
    avg(ok)                                  AS ok_fraction,
    last_value(ports_total ORDER BY time)    AS ports_total,
    last_value(ports_ok ORDER BY time)       AS ports_ok,
    last_value(ports_degraded ORDER BY time) AS ports_degraded,
    last_value(ports_errored ORDER BY time)  AS ports_errored
FROM ethernet
WHERE
    time > now() - INTERVAL '7 days'
GROUP BY bucket
ORDER BY bucket;
