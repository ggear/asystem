--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- interest/rate [interest and inflation rates published by the Reserve Bank of Australia] every 1d, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    time_bucket('1 day', time)                                                      AS "Bucket",
    entity                                                                          AS "Entity",
    round((avg(value) FILTER (WHERE type = 'mean' AND period = '1mo'))::numeric, 1) AS "Mean 1mo",
    round((avg(value) FILTER (WHERE type = 'mean' AND period = '1y'))::numeric, 1)  AS "Mean 1y",
    round((avg(value) FILTER (WHERE type = 'mean' AND period = '5y'))::numeric, 1)  AS "Mean 5y",
    round((avg(value) FILTER (WHERE type = 'mean' AND period = '10y'))::numeric, 1) AS "Mean 10y",
    round((avg(value) FILTER (WHERE type = 'mean' AND period = '20y'))::numeric, 1) AS "Mean 20y",
    round((avg(value) FILTER (WHERE type = 'mean' AND period = '40y'))::numeric, 1) AS "Mean 40y"
FROM interest
WHERE
    type IN ('mean')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM interest) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;
