--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- certificate/endpoint [certificate health across the monitored endpoints] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time)                     AS "Bucket",
    round(avg(ok), 1)                                    AS "Ok Fraction",
    round(last_value(score ORDER BY time), 1)            AS "Score",
    round(avg(min_expiry_days), 1)                       AS "Min Expiry Days Avg",
    round(min(min_expiry_days), 1)                       AS "Min Expiry Days Min",
    round(max(min_expiry_days), 1)                       AS "Min Expiry Days Max",
    round(last_value(endpoints_total ORDER BY time), 1)  AS "Endpoints Total",
    round(last_value(endpoints_failed ORDER BY time), 1) AS "Endpoints Failed"
FROM certificate
WHERE
    time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM certificate) - INTERVAL '1 day'
GROUP BY "Bucket"
ORDER BY "Bucket";
