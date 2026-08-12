--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- weewx/console [weather station console link health, one row per console] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    console                          AS "Console",
    round(avg(fresh), 1)             AS "Fresh Fraction",
    round(avg(quality_pct), 1)       AS "Quality Pct Avg",
    round(min(quality_pct), 1)       AS "Quality Pct Min",
    round(max(quality_pct), 1)       AS "Quality Pct Max"
FROM weewx
WHERE
    module = 'network'
    AND console IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weewx) - INTERVAL '1 day'
GROUP BY "Bucket", console
ORDER BY "Bucket", console;
