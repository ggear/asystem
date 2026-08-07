--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- equity/ticker [equity prices and volumes downloaded per ticker] every 1d, bucketed [1 day] across the newest two buckets
-- part 1 of 3:
SELECT
    time_bucket('1 day', time)                                                                    AS "Bucket",
    entity                                                                                        AS "Entity",
    round((avg(value) FILTER (WHERE type = 'market-volume-spot'))::numeric, 1)                    AS "Market Volume Spot",
    round((avg(value) FILTER (WHERE type = 'price-close'))::numeric, 1)                           AS "Price Close",
    round((avg(value) FILTER (WHERE type = 'price-close-base'))::numeric, 1)                      AS "Price Close Base",
    round((avg(value) FILTER (WHERE type = 'price-close-spot'))::numeric, 1)                      AS "Price Close Spot",
    round((avg(value) FILTER (WHERE type = 'price-close-1d-change-percentage'))::numeric, 1)      AS "Price Close 1d Change Percentage",
    round((avg(value) FILTER (WHERE type = 'price-close-base-1d-change-percentage'))::numeric, 1) AS "Price Close Base 1d Change Percentage",
    round((avg(value) FILTER (WHERE type = 'price-close-spot-1d-change-percentage'))::numeric, 1) AS "Price Close Spot 1d Change Percentage",
    round((avg(value) FILTER (WHERE type = 'price-close-30d-change-percentage'))::numeric, 1)     AS "Price Close 30d Change Percentage"
FROM equity
WHERE
    type IN ('market-volume-spot', 'price-close', 'price-close-1d-change-percentage', 'price-close-30d-change-percentage', 'price-close-base', 'price-close-base-1d-change-percentage', 'price-close-spot', 'price-close-spot-1d-change-percentage')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM equity) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;

-- equity/ticker [equity prices and volumes downloaded per ticker] every 1d, bucketed [1 day] across the newest two buckets
-- part 2 of 3:
SELECT
    time_bucket('1 day', time)                                                                     AS "Bucket",
    entity                                                                                         AS "Entity",
    round((avg(value) FILTER (WHERE type = 'price-close-base-30d-change-percentage'))::numeric, 1) AS "Price Close Base 30d Change Percentage",
    round((avg(value) FILTER (WHERE type = 'price-close-spot-30d-change-percentage'))::numeric, 1) AS "Price Close Spot 30d Change Percentage",
    round((avg(value) FILTER (WHERE type = 'price-close-90d-change-percentage'))::numeric, 1)      AS "Price Close 90d Change Percentage",
    round((avg(value) FILTER (WHERE type = 'price-close-base-90d-change-percentage'))::numeric, 1) AS "Price Close Base 90d Change Percentage",
    round((avg(value) FILTER (WHERE type = 'price-close-spot-90d-change-percentage'))::numeric, 1) AS "Price Close Spot 90d Change Percentage",
    round((avg(value) FILTER (WHERE type = 'price-close-365d-change-percentage'))::numeric, 1)     AS "Price Close 365d Change Percentage"
FROM equity
WHERE
    type IN ('price-close-365d-change-percentage', 'price-close-90d-change-percentage', 'price-close-base-30d-change-percentage', 'price-close-base-90d-change-percentage', 'price-close-spot-30d-change-percentage', 'price-close-spot-90d-change-percentage')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM equity) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;

-- equity/ticker [equity prices and volumes downloaded per ticker] every 1d, bucketed [1 day] across the newest two buckets
-- part 3 of 3:
SELECT
    time_bucket('1 day', time)                                                                      AS "Bucket",
    entity                                                                                          AS "Entity",
    round((avg(value) FILTER (WHERE type = 'price-close-base-365d-change-percentage'))::numeric, 1) AS "Price Close Base 365d Change Percentage",
    round((avg(value) FILTER (WHERE type = 'price-close-spot-365d-change-percentage'))::numeric, 1) AS "Price Close Spot 365d Change Percentage"
FROM equity
WHERE
    type IN ('price-close-base-365d-change-percentage', 'price-close-spot-365d-change-percentage')
    AND time >= CURRENT_DATE - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM equity) - INTERVAL '1 day'
GROUP BY "Bucket", entity
ORDER BY "Bucket", entity;
