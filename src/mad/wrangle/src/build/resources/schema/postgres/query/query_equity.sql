--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- equity/ticker [equity prices and volumes downloaded per ticker]
-- every query below is deliberately rich but row bounded, so a paste into psql stays readable
-- coverage, one row per declared series with its span, density and gap count
WITH bounds AS (
    SELECT
        type,
        period,
        unit,
        entity,
        min(time) AS oldest,
        max(time) AS newest,
        count(*)  AS rows_total
    FROM equity
    GROUP BY type, period, unit, entity
),
gaps AS (
    SELECT
        type,
        period,
        unit,
        entity,
        count(*) FILTER (WHERE step > expected) AS gaps_total
    FROM (
        SELECT
            type,
            period,
            unit,
            entity,
            time - lag(time) OVER (PARTITION BY type, period, unit, entity ORDER BY time) AS step,
            1                                                                             AS expected
        FROM equity
    ) AS stepped
    GROUP BY type, period, unit, entity
)
SELECT
    b.type,
    b.period,
    b.unit,
    count(*)          AS entities,
    sum(b.rows_total) AS rows_total,
    min(b.oldest)     AS oldest,
    max(b.newest)     AS newest,
    sum(g.gaps_total) AS gaps_total
FROM bounds AS b JOIN gaps AS g USING (type, period, unit, entity)
GROUP BY b.type, b.period, b.unit
ORDER BY b.type, b.period, b.unit;

-- latest reading per declared series, with its rank against the trailing year
SELECT DISTINCT ON (type, period, unit, entity)
    type,
    period,
    unit,
    entity,
    time,
    value,
    percent_rank() OVER (PARTITION BY type, period, unit, entity ORDER BY value) AS pct_rank_year
FROM equity
WHERE
    time >= CURRENT_DATE - INTERVAL '1 year'
ORDER BY type, period, unit, entity, time DESC;

-- monthly distribution per series, quartiles and swing, last year only
SELECT
    time_bucket('1 month', time)                        AS bucket,
    type,
    period,
    unit,
    count(*)                                            AS rows_total,
    avg(value)                                          AS mean,
    percentile_cont(0.25) WITHIN GROUP (ORDER BY value) AS p25,
    percentile_cont(0.50) WITHIN GROUP (ORDER BY value) AS median,
    percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75,
    max(value) - min(value)                             AS swing
FROM equity
WHERE
    time >= CURRENT_DATE - INTERVAL '1 year'
GROUP BY bucket, type, period, unit
ORDER BY bucket DESC, type, period, unit
LIMIT 50;

-- biggest movers, each series compared against its own trailing 30 reading mean
WITH trailing_mean AS (
    SELECT
        type,
        period,
        unit,
        entity,
        time,
        value,
        avg(value) OVER (PARTITION BY type, period, unit, entity ORDER BY time ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING) AS mean_30
    FROM equity
    WHERE
        time >= CURRENT_DATE - INTERVAL '90 days'
)
SELECT
    type,
    period,
    unit,
    entity,
    time,
    value,
    mean_30,
    value - mean_30 AS drift
FROM trailing_mean
WHERE
    mean_30 IS NOT NULL
ORDER BY abs(value - mean_30) DESC
LIMIT 20;

-- staleness, series whose newest reading is behind the table as a whole
SELECT
    type,
    period,
    unit,
    entity,
    max(time)                                  AS newest,
    (SELECT max(time) FROM equity) - max(time) AS behind
FROM equity
GROUP BY type, period, unit, entity
HAVING max(time) < (SELECT max(time) FROM equity)
ORDER BY behind DESC
LIMIT 20;

-- market-volume-spot [1d] in [$], yearly shape across entities
SELECT
    time_bucket('1 month', time) AS bucket,
    entity,
    avg(value)                   AS mean,
    min(value)                   AS low,
    max(value)                   AS high,
    count(*)                     AS rows_total
FROM equity
WHERE
    type = 'market-volume-spot'
    AND period = '1d'
    AND unit = '$'
    AND time >= CURRENT_DATE - INTERVAL '1 year'
GROUP BY bucket, entity
ORDER BY bucket DESC, entity
LIMIT 30;

-- price-close [1d] in [$], yearly shape across entities
SELECT
    time_bucket('1 month', time) AS bucket,
    entity,
    avg(value)                   AS mean,
    min(value)                   AS low,
    max(value)                   AS high,
    count(*)                     AS rows_total
FROM equity
WHERE
    type = 'price-close'
    AND period = '1d'
    AND unit = '$'
    AND time >= CURRENT_DATE - INTERVAL '1 year'
GROUP BY bucket, entity
ORDER BY bucket DESC, entity
LIMIT 30;

-- price-close-base [1d] in [$], yearly shape across entities
SELECT
    time_bucket('1 month', time) AS bucket,
    entity,
    avg(value)                   AS mean,
    min(value)                   AS low,
    max(value)                   AS high,
    count(*)                     AS rows_total
FROM equity
WHERE
    type = 'price-close-base'
    AND period = '1d'
    AND unit = '$'
    AND time >= CURRENT_DATE - INTERVAL '1 year'
GROUP BY bucket, entity
ORDER BY bucket DESC, entity
LIMIT 30;

-- price-close-spot [1d] in [$], yearly shape across entities
SELECT
    time_bucket('1 month', time) AS bucket,
    entity,
    avg(value)                   AS mean,
    min(value)                   AS low,
    max(value)                   AS high,
    count(*)                     AS rows_total
FROM equity
WHERE
    type = 'price-close-spot'
    AND period = '1d'
    AND unit = '$'
    AND time >= CURRENT_DATE - INTERVAL '1 year'
GROUP BY bucket, entity
ORDER BY bucket DESC, entity
LIMIT 30;

-- price-close-1d-change-percentage [1d] in [%], yearly shape across entities
SELECT
    time_bucket('1 month', time) AS bucket,
    entity,
    avg(value)                   AS mean,
    min(value)                   AS low,
    max(value)                   AS high,
    count(*)                     AS rows_total
FROM equity
WHERE
    type = 'price-close-1d-change-percentage'
    AND period = '1d'
    AND unit = '%'
    AND time >= CURRENT_DATE - INTERVAL '1 year'
GROUP BY bucket, entity
ORDER BY bucket DESC, entity
LIMIT 30;

-- price-close-base-1d-change-percentage [1d] in [%], yearly shape across entities
SELECT
    time_bucket('1 month', time) AS bucket,
    entity,
    avg(value)                   AS mean,
    min(value)                   AS low,
    max(value)                   AS high,
    count(*)                     AS rows_total
FROM equity
WHERE
    type = 'price-close-base-1d-change-percentage'
    AND period = '1d'
    AND unit = '%'
    AND time >= CURRENT_DATE - INTERVAL '1 year'
GROUP BY bucket, entity
ORDER BY bucket DESC, entity
LIMIT 30;

-- price-close-spot-1d-change-percentage [1d] in [%], yearly shape across entities
SELECT
    time_bucket('1 month', time) AS bucket,
    entity,
    avg(value)                   AS mean,
    min(value)                   AS low,
    max(value)                   AS high,
    count(*)                     AS rows_total
FROM equity
WHERE
    type = 'price-close-spot-1d-change-percentage'
    AND period = '1d'
    AND unit = '%'
    AND time >= CURRENT_DATE - INTERVAL '1 year'
GROUP BY bucket, entity
ORDER BY bucket DESC, entity
LIMIT 30;

-- price-close-30d-change-percentage [30d] in [%], yearly shape across entities
SELECT
    time_bucket('1 month', time) AS bucket,
    entity,
    avg(value)                   AS mean,
    min(value)                   AS low,
    max(value)                   AS high,
    count(*)                     AS rows_total
FROM equity
WHERE
    type = 'price-close-30d-change-percentage'
    AND period = '30d'
    AND unit = '%'
    AND time >= CURRENT_DATE - INTERVAL '1 year'
GROUP BY bucket, entity
ORDER BY bucket DESC, entity
LIMIT 30;

-- price-close-base-30d-change-percentage [30d] in [%], yearly shape across entities
SELECT
    time_bucket('1 month', time) AS bucket,
    entity,
    avg(value)                   AS mean,
    min(value)                   AS low,
    max(value)                   AS high,
    count(*)                     AS rows_total
FROM equity
WHERE
    type = 'price-close-base-30d-change-percentage'
    AND period = '30d'
    AND unit = '%'
    AND time >= CURRENT_DATE - INTERVAL '1 year'
GROUP BY bucket, entity
ORDER BY bucket DESC, entity
LIMIT 30;

-- price-close-spot-30d-change-percentage [30d] in [%], yearly shape across entities
SELECT
    time_bucket('1 month', time) AS bucket,
    entity,
    avg(value)                   AS mean,
    min(value)                   AS low,
    max(value)                   AS high,
    count(*)                     AS rows_total
FROM equity
WHERE
    type = 'price-close-spot-30d-change-percentage'
    AND period = '30d'
    AND unit = '%'
    AND time >= CURRENT_DATE - INTERVAL '1 year'
GROUP BY bucket, entity
ORDER BY bucket DESC, entity
LIMIT 30;

-- price-close-90d-change-percentage [90d] in [%], yearly shape across entities
SELECT
    time_bucket('1 month', time) AS bucket,
    entity,
    avg(value)                   AS mean,
    min(value)                   AS low,
    max(value)                   AS high,
    count(*)                     AS rows_total
FROM equity
WHERE
    type = 'price-close-90d-change-percentage'
    AND period = '90d'
    AND unit = '%'
    AND time >= CURRENT_DATE - INTERVAL '1 year'
GROUP BY bucket, entity
ORDER BY bucket DESC, entity
LIMIT 30;

-- price-close-base-90d-change-percentage [90d] in [%], yearly shape across entities
SELECT
    time_bucket('1 month', time) AS bucket,
    entity,
    avg(value)                   AS mean,
    min(value)                   AS low,
    max(value)                   AS high,
    count(*)                     AS rows_total
FROM equity
WHERE
    type = 'price-close-base-90d-change-percentage'
    AND period = '90d'
    AND unit = '%'
    AND time >= CURRENT_DATE - INTERVAL '1 year'
GROUP BY bucket, entity
ORDER BY bucket DESC, entity
LIMIT 30;

-- price-close-spot-90d-change-percentage [90d] in [%], yearly shape across entities
SELECT
    time_bucket('1 month', time) AS bucket,
    entity,
    avg(value)                   AS mean,
    min(value)                   AS low,
    max(value)                   AS high,
    count(*)                     AS rows_total
FROM equity
WHERE
    type = 'price-close-spot-90d-change-percentage'
    AND period = '90d'
    AND unit = '%'
    AND time >= CURRENT_DATE - INTERVAL '1 year'
GROUP BY bucket, entity
ORDER BY bucket DESC, entity
LIMIT 30;

-- price-close-365d-change-percentage [365d] in [%], yearly shape across entities
SELECT
    time_bucket('1 month', time) AS bucket,
    entity,
    avg(value)                   AS mean,
    min(value)                   AS low,
    max(value)                   AS high,
    count(*)                     AS rows_total
FROM equity
WHERE
    type = 'price-close-365d-change-percentage'
    AND period = '365d'
    AND unit = '%'
    AND time >= CURRENT_DATE - INTERVAL '1 year'
GROUP BY bucket, entity
ORDER BY bucket DESC, entity
LIMIT 30;

-- price-close-base-365d-change-percentage [365d] in [%], yearly shape across entities
SELECT
    time_bucket('1 month', time) AS bucket,
    entity,
    avg(value)                   AS mean,
    min(value)                   AS low,
    max(value)                   AS high,
    count(*)                     AS rows_total
FROM equity
WHERE
    type = 'price-close-base-365d-change-percentage'
    AND period = '365d'
    AND unit = '%'
    AND time >= CURRENT_DATE - INTERVAL '1 year'
GROUP BY bucket, entity
ORDER BY bucket DESC, entity
LIMIT 30;

-- price-close-spot-365d-change-percentage [365d] in [%], yearly shape across entities
SELECT
    time_bucket('1 month', time) AS bucket,
    entity,
    avg(value)                   AS mean,
    min(value)                   AS low,
    max(value)                   AS high,
    count(*)                     AS rows_total
FROM equity
WHERE
    type = 'price-close-spot-365d-change-percentage'
    AND period = '365d'
    AND unit = '%'
    AND time >= CURRENT_DATE - INTERVAL '1 year'
GROUP BY bucket, entity
ORDER BY bucket DESC, entity
LIMIT 30;
