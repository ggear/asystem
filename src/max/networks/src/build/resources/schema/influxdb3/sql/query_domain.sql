--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- domain/resolver [public DNS resolution of the monitored domain across the public resolvers] every 15m
SELECT
    date_bin(INTERVAL '1 hour', time)          AS bucket,
    avg(ok)                                    AS ok_fraction,
    last_value(score ORDER BY time)            AS score,
    last_value(resolvers_total ORDER BY time)  AS resolvers_total,
    last_value(resolvers_ok ORDER BY time)     AS resolvers_ok,
    last_value(resolvers_failed ORDER BY time) AS resolvers_failed
FROM domain
WHERE
    time > now() - INTERVAL '7 days'
GROUP BY bucket
ORDER BY bucket;
