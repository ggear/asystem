--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- domain/resolver [public DNS resolution of the monitored domain, one row per public resolver] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    resolver                                                 AS "Resolver",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(ok), 1)                                        AS "Ok Fraction",
    count(ok)                                                AS "Ok Count",
    count(DISTINCT ok)                                       AS "Ok Distinct",
    round(avg(resolved), 1)                                  AS "Resolved Fraction",
    count(resolved)                                          AS "Resolved Count",
    count(DISTINCT resolved)                                 AS "Resolved Distinct",
    round(avg(latency_ms), 1)                                AS "Latency Ms Avg",
    round(min(latency_ms), 1)                                AS "Latency Ms Min",
    round(max(latency_ms), 1)                                AS "Latency Ms Max",
    count(latency_ms)                                        AS "Latency Ms Count",
    count(DISTINCT latency_ms)                               AS "Latency Ms Distinct"
FROM domain
WHERE
    module = 'network'
    AND resolver IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM domain) - INTERVAL '1 day'
GROUP BY "Bucket", resolver
ORDER BY "Bucket", resolver;
