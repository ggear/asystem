--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- interest/rate [interest and inflation rates published by the Reserve Bank of Australia] every 1d, bucketed [1 day] across the newest two buckets
-- part 1 of 2:
SELECT
    time_bucket('1 day', time)                                                      AS "Bucket",
    entity                                                                          AS "Entity",
    count(DISTINCT time)                                                            AS "Rows",
    min(time)                                                                       AS "Oldest",
    max(time)                                                                       AS "Newest",
    round((avg(value) FILTER (WHERE type = 'mean' AND period = '1mo'))::numeric, 1) AS "Mean 1mo",
    count(*) FILTER (WHERE type = 'mean' AND period = '1mo')                        AS "Mean 1mo Count",
    count(DISTINCT value) FILTER (WHERE type = 'mean' AND period = '1mo')           AS "Mean 1mo Distinct",
    round((avg(value) FILTER (WHERE type = 'mean' AND period = '1y'))::numeric, 1)  AS "Mean 1y",
    count(*) FILTER (WHERE type = 'mean' AND period = '1y')                         AS "Mean 1y Count",
    count(DISTINCT value) FILTER (WHERE type = 'mean' AND period = '1y')            AS "Mean 1y Distinct",
    round((avg(value) FILTER (WHERE type = 'mean' AND period = '5y'))::numeric, 1)  AS "Mean 5y",
    count(*) FILTER (WHERE type = 'mean' AND period = '5y')                         AS "Mean 5y Count",
    count(DISTINCT value) FILTER (WHERE type = 'mean' AND period = '5y')            AS "Mean 5y Distinct",
    round((avg(value) FILTER (WHERE type = 'mean' AND period = '10y'))::numeric, 1) AS "Mean 10y",
    count(*) FILTER (WHERE type = 'mean' AND period = '10y')                        AS "Mean 10y Count",
    count(DISTINCT value) FILTER (WHERE type = 'mean' AND period = '10y')           AS "Mean 10y Distinct"
FROM interest
WHERE
    type IN ('mean')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM interest) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;

-- interest/rate [interest and inflation rates published by the Reserve Bank of Australia] every 1d, bucketed [1 day] across the newest two buckets
-- part 2 of 2:
SELECT
    time_bucket('1 day', time)                                                      AS "Bucket",
    entity                                                                          AS "Entity",
    count(DISTINCT time)                                                            AS "Rows",
    min(time)                                                                       AS "Oldest",
    max(time)                                                                       AS "Newest",
    round((avg(value) FILTER (WHERE type = 'mean' AND period = '20y'))::numeric, 1) AS "Mean 20y",
    count(*) FILTER (WHERE type = 'mean' AND period = '20y')                        AS "Mean 20y Count",
    count(DISTINCT value) FILTER (WHERE type = 'mean' AND period = '20y')           AS "Mean 20y Distinct",
    round((avg(value) FILTER (WHERE type = 'mean' AND period = '40y'))::numeric, 1) AS "Mean 40y",
    count(*) FILTER (WHERE type = 'mean' AND period = '40y')                        AS "Mean 40y Count",
    count(DISTINCT value) FILTER (WHERE type = 'mean' AND period = '40y')           AS "Mean 40y Distinct"
FROM interest
WHERE
    type IN ('mean')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM interest) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;
