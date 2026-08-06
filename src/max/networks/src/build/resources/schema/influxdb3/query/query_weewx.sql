--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- weewx/console [the weather station console link and its health] every 15m
SELECT
    date_bin(INTERVAL '1 hour', time) AS bucket,
    avg(ok)                           AS ok_fraction,
    last_value(score ORDER BY time)   AS score
FROM weewx
WHERE
    time > now() - INTERVAL '7 days'
GROUP BY bucket
ORDER BY bucket;
