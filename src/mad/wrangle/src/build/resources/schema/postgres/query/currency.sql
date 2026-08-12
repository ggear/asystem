--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- currency/rate [foreign exchange rates published by the Reserve Bank of Australia] every 1d, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    time_bucket('1 day', time)                                                        AS "Bucket",
    entity                                                                            AS "Entity",
    round((avg(value) FILTER (WHERE type = 'snapshot'))::numeric, 1)                  AS "Snapshot",
    round((avg(value) FILTER (WHERE type = 'delta' AND period = '1d'))::numeric, 1)   AS "Delta 1d",
    round((avg(value) FILTER (WHERE type = 'delta' AND period = '7d'))::numeric, 1)   AS "Delta 7d",
    round((avg(value) FILTER (WHERE type = 'delta' AND period = '30d'))::numeric, 1)  AS "Delta 30d",
    round((avg(value) FILTER (WHERE type = 'delta' AND period = '365d'))::numeric, 1) AS "Delta 365d"
FROM currency
WHERE
    type IN ('delta', 'snapshot')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM currency) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;
