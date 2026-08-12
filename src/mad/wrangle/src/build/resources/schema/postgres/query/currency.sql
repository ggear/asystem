--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- currency/rate [foreign exchange rates published by the Reserve Bank of Australia] every 1d, bucketed [1 day] across the newest two buckets
-- part 1 of 2:
SELECT
    time_bucket('1 day', time)                                                       AS "Bucket",
    entity                                                                           AS "Entity",
    count(DISTINCT time)                                                             AS "Rows",
    min(time)                                                                        AS "Oldest",
    max(time)                                                                        AS "Newest",
    round((avg(value) FILTER (WHERE type = 'snapshot'))::numeric, 1)                 AS "Snapshot",
    count(*) FILTER (WHERE type = 'snapshot')                                        AS "Snapshot Count",
    count(DISTINCT value) FILTER (WHERE type = 'snapshot')                           AS "Snapshot Distinct",
    round((avg(value) FILTER (WHERE type = 'delta' AND period = '1d'))::numeric, 1)  AS "Delta 1d",
    count(*) FILTER (WHERE type = 'delta' AND period = '1d')                         AS "Delta 1d Count",
    count(DISTINCT value) FILTER (WHERE type = 'delta' AND period = '1d')            AS "Delta 1d Distinct",
    round((avg(value) FILTER (WHERE type = 'delta' AND period = '7d'))::numeric, 1)  AS "Delta 7d",
    count(*) FILTER (WHERE type = 'delta' AND period = '7d')                         AS "Delta 7d Count",
    count(DISTINCT value) FILTER (WHERE type = 'delta' AND period = '7d')            AS "Delta 7d Distinct",
    round((avg(value) FILTER (WHERE type = 'delta' AND period = '30d'))::numeric, 1) AS "Delta 30d",
    count(*) FILTER (WHERE type = 'delta' AND period = '30d')                        AS "Delta 30d Count",
    count(DISTINCT value) FILTER (WHERE type = 'delta' AND period = '30d')           AS "Delta 30d Distinct"
FROM currency
WHERE
    type IN ('delta', 'snapshot')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM currency) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;

-- currency/rate [foreign exchange rates published by the Reserve Bank of Australia] every 1d, bucketed [1 day] across the newest two buckets
-- part 2 of 2:
SELECT
    time_bucket('1 day', time)                                                        AS "Bucket",
    entity                                                                            AS "Entity",
    count(DISTINCT time)                                                              AS "Rows",
    min(time)                                                                         AS "Oldest",
    max(time)                                                                         AS "Newest",
    round((avg(value) FILTER (WHERE type = 'delta' AND period = '365d'))::numeric, 1) AS "Delta 365d",
    count(*) FILTER (WHERE type = 'delta' AND period = '365d')                        AS "Delta 365d Count",
    count(DISTINCT value) FILTER (WHERE type = 'delta' AND period = '365d')           AS "Delta 365d Distinct"
FROM currency
WHERE
    type IN ('delta')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM currency) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;
