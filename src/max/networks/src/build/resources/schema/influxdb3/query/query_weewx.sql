--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- weewx/console [the weather station console link and its health] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time)          AS "Bucket",
    round(avg(ok), 1)                         AS "Ok Fraction",
    round(last_value(score ORDER BY time), 1) AS "Score"
FROM weewx
WHERE
    time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weewx) - INTERVAL '1 day'
GROUP BY "Bucket"
ORDER BY "Bucket";
