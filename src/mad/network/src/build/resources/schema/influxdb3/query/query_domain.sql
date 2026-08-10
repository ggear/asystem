--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- domain/resolver [public DNS resolution of the monitored domain, one row per public resolver] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    resolver                         AS "Resolver",
    round(avg(ok), 1)                AS "Ok Fraction",
    round(avg(resolved), 1)          AS "Resolved Fraction",
    round(avg(latency_ms), 1)        AS "Latency Ms Avg",
    round(min(latency_ms), 1)        AS "Latency Ms Min",
    round(max(latency_ms), 1)        AS "Latency Ms Max"
FROM domain
WHERE
    resolver IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM domain) - INTERVAL '1 day'
GROUP BY "Bucket", resolver
ORDER BY "Bucket", resolver;
