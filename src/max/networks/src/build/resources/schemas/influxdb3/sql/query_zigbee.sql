--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- zigbee/bridge [coordinator state and the mesh it reports] every 15m
SELECT
    date_bin(INTERVAL '1 hour', time)       AS bucket,
    avg(ok)                                 AS ok_fraction,
    last_value(score ORDER BY time)         AS score,
    last_value(devices_total ORDER BY time) AS devices_total,
    last_value(devices_ok ORDER BY time)    AS devices_ok,
    last_value(devices_weak ORDER BY time)  AS devices_weak,
    avg(avg_lqi)                            AS avg_lqi_avg,
    min(avg_lqi)                            AS avg_lqi_min,
    max(avg_lqi)                            AS avg_lqi_max
FROM zigbee
WHERE
    time > now() - INTERVAL '7 days'
GROUP BY bucket
ORDER BY bucket;
