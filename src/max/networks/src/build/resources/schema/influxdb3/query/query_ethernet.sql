--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- ethernet/port [switch port health across the monitored ports] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time)                   AS "Bucket",
    round(last_value(score ORDER BY time), 1)          AS "Score",
    round(avg(ok), 1)                                  AS "Ok Fraction",
    round(last_value(ports_total ORDER BY time), 1)    AS "Ports Total",
    round(last_value(ports_ok ORDER BY time), 1)       AS "Ports Ok",
    round(last_value(ports_degraded ORDER BY time), 1) AS "Ports Degraded",
    round(last_value(ports_errored ORDER BY time), 1)  AS "Ports Errored"
FROM ethernet
WHERE
    time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM ethernet) - INTERVAL '1 day'
GROUP BY "Bucket"
ORDER BY "Bucket";
