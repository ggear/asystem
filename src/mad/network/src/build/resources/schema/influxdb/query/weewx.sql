--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- weewx/console [weather station console link health, one row per console] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    console                                                  AS "Console",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(fresh), 1)                                     AS "Fresh Fraction",
    count(fresh)                                             AS "Fresh Count",
    count(DISTINCT fresh)                                    AS "Fresh Distinct",
    round(avg(quality_pct), 1)                               AS "Quality Pct Avg",
    round(min(quality_pct), 1)                               AS "Quality Pct Min",
    round(max(quality_pct), 1)                               AS "Quality Pct Max",
    count(quality_pct)                                       AS "Quality Pct Count",
    count(DISTINCT quality_pct)                              AS "Quality Pct Distinct"
FROM weewx
WHERE
    module = 'network'
    AND console IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weewx) - INTERVAL '1 day'
GROUP BY "Bucket", console
ORDER BY "Bucket", console;
