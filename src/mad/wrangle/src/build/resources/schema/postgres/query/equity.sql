--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- equity/ticker [equity prices and volumes downloaded per ticker] every 1d, bucketed [1 day] across the newest two buckets
-- part 1 of 14:
SELECT
    time_bucket('1 day', time)                                                 AS "Bucket",
    entity                                                                     AS "Entity",
    count(DISTINCT time)                                                       AS "Rows",
    min(time)                                                                  AS "Oldest",
    max(time)                                                                  AS "Newest",
    round((avg(value) FILTER (WHERE type = 'market-volume-spot'))::numeric, 1) AS "Market Volume Spot",
    count(*) FILTER (WHERE type = 'market-volume-spot')                        AS "Market Volume Spot Count",
    count(DISTINCT value) FILTER (WHERE type = 'market-volume-spot')           AS "Market Volume Spot Distinct",
    round((avg(value) FILTER (WHERE type = 'price-close'))::numeric, 1)        AS "Price Close",
    count(*) FILTER (WHERE type = 'price-close')                               AS "Price Close Count",
    count(DISTINCT value) FILTER (WHERE type = 'price-close')                  AS "Price Close Distinct"
FROM equity
WHERE
    type IN ('market-volume-spot', 'price-close')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM equity) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;

-- equity/ticker [equity prices and volumes downloaded per ticker] every 1d, bucketed [1 day] across the newest two buckets
-- part 2 of 14:
SELECT
    time_bucket('1 day', time)                                               AS "Bucket",
    entity                                                                   AS "Entity",
    count(DISTINCT time)                                                     AS "Rows",
    min(time)                                                                AS "Oldest",
    max(time)                                                                AS "Newest",
    round((avg(value) FILTER (WHERE type = 'price-close-base'))::numeric, 1) AS "Price Close Base",
    count(*) FILTER (WHERE type = 'price-close-base')                        AS "Price Close Base Count",
    count(DISTINCT value) FILTER (WHERE type = 'price-close-base')           AS "Price Close Base Distinct",
    round((avg(value) FILTER (WHERE type = 'price-close-spot'))::numeric, 1) AS "Price Close Spot",
    count(*) FILTER (WHERE type = 'price-close-spot')                        AS "Price Close Spot Count",
    count(DISTINCT value) FILTER (WHERE type = 'price-close-spot')           AS "Price Close Spot Distinct"
FROM equity
WHERE
    type IN ('price-close-base', 'price-close-spot')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM equity) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;

-- equity/ticker [equity prices and volumes downloaded per ticker] every 1d, bucketed [1 day] across the newest two buckets
-- part 3 of 14:
SELECT
    time_bucket('1 day', time)                                                               AS "Bucket",
    entity                                                                                   AS "Entity",
    count(DISTINCT time)                                                                     AS "Rows",
    min(time)                                                                                AS "Oldest",
    max(time)                                                                                AS "Newest",
    round((avg(value) FILTER (WHERE type = 'price-close-1d-change-percentage'))::numeric, 1) AS "Price Close 1d Change Percentage",
    count(*) FILTER (WHERE type = 'price-close-1d-change-percentage')                        AS "Price Close 1d Change Percentage Count",
    count(DISTINCT value) FILTER (WHERE type = 'price-close-1d-change-percentage')           AS "Price Close 1d Change Percentage Distinct"
FROM equity
WHERE
    type IN ('price-close-1d-change-percentage')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM equity) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;

-- equity/ticker [equity prices and volumes downloaded per ticker] every 1d, bucketed [1 day] across the newest two buckets
-- part 4 of 14:
SELECT
    time_bucket('1 day', time)                                                                    AS "Bucket",
    entity                                                                                        AS "Entity",
    count(DISTINCT time)                                                                          AS "Rows",
    min(time)                                                                                     AS "Oldest",
    max(time)                                                                                     AS "Newest",
    round((avg(value) FILTER (WHERE type = 'price-close-base-1d-change-percentage'))::numeric, 1) AS "Price Close Base 1d Change Percentage",
    count(*) FILTER (WHERE type = 'price-close-base-1d-change-percentage')                        AS "Price Close Base 1d Change Percentage Count",
    count(DISTINCT value) FILTER (WHERE type = 'price-close-base-1d-change-percentage')           AS "Price Close Base 1d Change Percentage Distinct"
FROM equity
WHERE
    type IN ('price-close-base-1d-change-percentage')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM equity) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;

-- equity/ticker [equity prices and volumes downloaded per ticker] every 1d, bucketed [1 day] across the newest two buckets
-- part 5 of 14:
SELECT
    time_bucket('1 day', time)                                                                    AS "Bucket",
    entity                                                                                        AS "Entity",
    count(DISTINCT time)                                                                          AS "Rows",
    min(time)                                                                                     AS "Oldest",
    max(time)                                                                                     AS "Newest",
    round((avg(value) FILTER (WHERE type = 'price-close-spot-1d-change-percentage'))::numeric, 1) AS "Price Close Spot 1d Change Percentage",
    count(*) FILTER (WHERE type = 'price-close-spot-1d-change-percentage')                        AS "Price Close Spot 1d Change Percentage Count",
    count(DISTINCT value) FILTER (WHERE type = 'price-close-spot-1d-change-percentage')           AS "Price Close Spot 1d Change Percentage Distinct"
FROM equity
WHERE
    type IN ('price-close-spot-1d-change-percentage')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM equity) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;

-- equity/ticker [equity prices and volumes downloaded per ticker] every 1d, bucketed [1 day] across the newest two buckets
-- part 6 of 14:
SELECT
    time_bucket('1 day', time)                                                                AS "Bucket",
    entity                                                                                    AS "Entity",
    count(DISTINCT time)                                                                      AS "Rows",
    min(time)                                                                                 AS "Oldest",
    max(time)                                                                                 AS "Newest",
    round((avg(value) FILTER (WHERE type = 'price-close-30d-change-percentage'))::numeric, 1) AS "Price Close 30d Change Percentage",
    count(*) FILTER (WHERE type = 'price-close-30d-change-percentage')                        AS "Price Close 30d Change Percentage Count",
    count(DISTINCT value) FILTER (WHERE type = 'price-close-30d-change-percentage')           AS "Price Close 30d Change Percentage Distinct"
FROM equity
WHERE
    type IN ('price-close-30d-change-percentage')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM equity) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;

-- equity/ticker [equity prices and volumes downloaded per ticker] every 1d, bucketed [1 day] across the newest two buckets
-- part 7 of 14:
SELECT
    time_bucket('1 day', time)                                                                     AS "Bucket",
    entity                                                                                         AS "Entity",
    count(DISTINCT time)                                                                           AS "Rows",
    min(time)                                                                                      AS "Oldest",
    max(time)                                                                                      AS "Newest",
    round((avg(value) FILTER (WHERE type = 'price-close-base-30d-change-percentage'))::numeric, 1) AS "Price Close Base 30d Change Percentage",
    count(*) FILTER (WHERE type = 'price-close-base-30d-change-percentage')                        AS "Price Close Base 30d Change Percentage Count",
    count(DISTINCT value) FILTER (WHERE type = 'price-close-base-30d-change-percentage')           AS "Price Close Base 30d Change Percentage Distinct"
FROM equity
WHERE
    type IN ('price-close-base-30d-change-percentage')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM equity) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;

-- equity/ticker [equity prices and volumes downloaded per ticker] every 1d, bucketed [1 day] across the newest two buckets
-- part 8 of 14:
SELECT
    time_bucket('1 day', time)                                                                     AS "Bucket",
    entity                                                                                         AS "Entity",
    count(DISTINCT time)                                                                           AS "Rows",
    min(time)                                                                                      AS "Oldest",
    max(time)                                                                                      AS "Newest",
    round((avg(value) FILTER (WHERE type = 'price-close-spot-30d-change-percentage'))::numeric, 1) AS "Price Close Spot 30d Change Percentage",
    count(*) FILTER (WHERE type = 'price-close-spot-30d-change-percentage')                        AS "Price Close Spot 30d Change Percentage Count",
    count(DISTINCT value) FILTER (WHERE type = 'price-close-spot-30d-change-percentage')           AS "Price Close Spot 30d Change Percentage Distinct"
FROM equity
WHERE
    type IN ('price-close-spot-30d-change-percentage')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM equity) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;

-- equity/ticker [equity prices and volumes downloaded per ticker] every 1d, bucketed [1 day] across the newest two buckets
-- part 9 of 14:
SELECT
    time_bucket('1 day', time)                                                                AS "Bucket",
    entity                                                                                    AS "Entity",
    count(DISTINCT time)                                                                      AS "Rows",
    min(time)                                                                                 AS "Oldest",
    max(time)                                                                                 AS "Newest",
    round((avg(value) FILTER (WHERE type = 'price-close-90d-change-percentage'))::numeric, 1) AS "Price Close 90d Change Percentage",
    count(*) FILTER (WHERE type = 'price-close-90d-change-percentage')                        AS "Price Close 90d Change Percentage Count",
    count(DISTINCT value) FILTER (WHERE type = 'price-close-90d-change-percentage')           AS "Price Close 90d Change Percentage Distinct"
FROM equity
WHERE
    type IN ('price-close-90d-change-percentage')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM equity) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;

-- equity/ticker [equity prices and volumes downloaded per ticker] every 1d, bucketed [1 day] across the newest two buckets
-- part 10 of 14:
SELECT
    time_bucket('1 day', time)                                                                     AS "Bucket",
    entity                                                                                         AS "Entity",
    count(DISTINCT time)                                                                           AS "Rows",
    min(time)                                                                                      AS "Oldest",
    max(time)                                                                                      AS "Newest",
    round((avg(value) FILTER (WHERE type = 'price-close-base-90d-change-percentage'))::numeric, 1) AS "Price Close Base 90d Change Percentage",
    count(*) FILTER (WHERE type = 'price-close-base-90d-change-percentage')                        AS "Price Close Base 90d Change Percentage Count",
    count(DISTINCT value) FILTER (WHERE type = 'price-close-base-90d-change-percentage')           AS "Price Close Base 90d Change Percentage Distinct"
FROM equity
WHERE
    type IN ('price-close-base-90d-change-percentage')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM equity) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;

-- equity/ticker [equity prices and volumes downloaded per ticker] every 1d, bucketed [1 day] across the newest two buckets
-- part 11 of 14:
SELECT
    time_bucket('1 day', time)                                                                     AS "Bucket",
    entity                                                                                         AS "Entity",
    count(DISTINCT time)                                                                           AS "Rows",
    min(time)                                                                                      AS "Oldest",
    max(time)                                                                                      AS "Newest",
    round((avg(value) FILTER (WHERE type = 'price-close-spot-90d-change-percentage'))::numeric, 1) AS "Price Close Spot 90d Change Percentage",
    count(*) FILTER (WHERE type = 'price-close-spot-90d-change-percentage')                        AS "Price Close Spot 90d Change Percentage Count",
    count(DISTINCT value) FILTER (WHERE type = 'price-close-spot-90d-change-percentage')           AS "Price Close Spot 90d Change Percentage Distinct"
FROM equity
WHERE
    type IN ('price-close-spot-90d-change-percentage')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM equity) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;

-- equity/ticker [equity prices and volumes downloaded per ticker] every 1d, bucketed [1 day] across the newest two buckets
-- part 12 of 14:
SELECT
    time_bucket('1 day', time)                                                                 AS "Bucket",
    entity                                                                                     AS "Entity",
    count(DISTINCT time)                                                                       AS "Rows",
    min(time)                                                                                  AS "Oldest",
    max(time)                                                                                  AS "Newest",
    round((avg(value) FILTER (WHERE type = 'price-close-365d-change-percentage'))::numeric, 1) AS "Price Close 365d Change Percentage",
    count(*) FILTER (WHERE type = 'price-close-365d-change-percentage')                        AS "Price Close 365d Change Percentage Count",
    count(DISTINCT value) FILTER (WHERE type = 'price-close-365d-change-percentage')           AS "Price Close 365d Change Percentage Distinct"
FROM equity
WHERE
    type IN ('price-close-365d-change-percentage')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM equity) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;

-- equity/ticker [equity prices and volumes downloaded per ticker] every 1d, bucketed [1 day] across the newest two buckets
-- part 13 of 14:
SELECT
    time_bucket('1 day', time)                                                                      AS "Bucket",
    entity                                                                                          AS "Entity",
    count(DISTINCT time)                                                                            AS "Rows",
    min(time)                                                                                       AS "Oldest",
    max(time)                                                                                       AS "Newest",
    round((avg(value) FILTER (WHERE type = 'price-close-base-365d-change-percentage'))::numeric, 1) AS "Price Close Base 365d Change Percentage",
    count(*) FILTER (WHERE type = 'price-close-base-365d-change-percentage')                        AS "Price Close Base 365d Change Percentage Count",
    count(DISTINCT value) FILTER (WHERE type = 'price-close-base-365d-change-percentage')           AS "Price Close Base 365d Change Percentage Distinct"
FROM equity
WHERE
    type IN ('price-close-base-365d-change-percentage')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM equity) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;

-- equity/ticker [equity prices and volumes downloaded per ticker] every 1d, bucketed [1 day] across the newest two buckets
-- part 14 of 14:
SELECT
    time_bucket('1 day', time)                                                                      AS "Bucket",
    entity                                                                                          AS "Entity",
    count(DISTINCT time)                                                                            AS "Rows",
    min(time)                                                                                       AS "Oldest",
    max(time)                                                                                       AS "Newest",
    round((avg(value) FILTER (WHERE type = 'price-close-spot-365d-change-percentage'))::numeric, 1) AS "Price Close Spot 365d Change Percentage",
    count(*) FILTER (WHERE type = 'price-close-spot-365d-change-percentage')                        AS "Price Close Spot 365d Change Percentage Count",
    count(DISTINCT value) FILTER (WHERE type = 'price-close-spot-365d-change-percentage')           AS "Price Close Spot 365d Change Percentage Distinct"
FROM equity
WHERE
    type IN ('price-close-spot-365d-change-percentage')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM equity) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;
