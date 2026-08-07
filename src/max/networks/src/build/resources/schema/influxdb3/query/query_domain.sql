--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- domain/resolver [public DNS resolution of the monitored domain across the public resolvers] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time)                     AS "Bucket",
    round(avg(ok), 1)                                    AS "Ok Fraction",
    round(last_value(score ORDER BY time), 1)            AS "Score",
    round(last_value(resolvers_total ORDER BY time), 1)  AS "Resolvers Total",
    round(last_value(resolvers_ok ORDER BY time), 1)     AS "Resolvers Ok",
    round(last_value(resolvers_failed ORDER BY time), 1) AS "Resolvers Failed"
FROM domain
WHERE
    time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM domain) - INTERVAL '1 day'
GROUP BY "Bucket"
ORDER BY "Bucket";
