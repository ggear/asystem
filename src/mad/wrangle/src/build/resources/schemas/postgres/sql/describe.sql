--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- dimensions
SELECT
    'currency/rate'        AS relation,
    'entity*'              AS dimension,
    '1d'                   AS cadence,
    5                      AS measures,
    5                      AS persisted,
    '3'                    AS declared,
    count(DISTINCT entity) AS observed,
    count(*)               AS rows,
    min(time)              AS oldest,
    max(time)              AS newest
FROM currency
WHERE
    type IN ('delta', 'snapshot')
UNION ALL
SELECT
    'interest/rate'        AS relation,
    'entity*'              AS dimension,
    '1d'                   AS cadence,
    6                      AS measures,
    6                      AS persisted,
    '3'                    AS declared,
    count(DISTINCT entity) AS observed,
    count(*)               AS rows,
    min(time)              AS oldest,
    max(time)              AS newest
FROM interest
WHERE
    type IN ('mean')
UNION ALL
SELECT
    'equity/ticker'        AS relation,
    'entity*'              AS dimension,
    '1d'                   AS cadence,
    16                     AS measures,
    16                     AS persisted,
    '-'                    AS declared,
    count(DISTINCT entity) AS observed,
    count(*)               AS rows,
    min(time)              AS oldest,
    max(time)              AS newest
FROM equity
WHERE
    type IN (
        'market-volume-spot', 'price-close', 'price-close-1d-change-percentage',
        'price-close-30d-change-percentage', 'price-close-365d-change-percentage',
        'price-close-90d-change-percentage', 'price-close-base',
        'price-close-base-1d-change-percentage', 'price-close-base-30d-change-percentage',
        'price-close-base-365d-change-percentage', 'price-close-base-90d-change-percentage',
        'price-close-spot', 'price-close-spot-1d-change-percentage',
        'price-close-spot-30d-change-percentage', 'price-close-spot-365d-change-percentage',
        'price-close-spot-90d-change-percentage'
    )
ORDER BY relation;

-- measures
SELECT
    'currency/rate'                                 AS relation,
    'snapshot'                                      AS measure,
    'float'                                         AS kind,
    '$'                                             AS unit,
    '1d'                                            AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM currency
WHERE
    type = 'snapshot'
    AND period = '1d'
    AND unit = '$'
UNION ALL
SELECT
    'currency/rate'                                 AS relation,
    'delta'                                         AS measure,
    'float'                                         AS kind,
    '%'                                             AS unit,
    '1d'                                            AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM currency
WHERE
    type = 'delta'
    AND period = '1d'
    AND unit = '%'
UNION ALL
SELECT
    'currency/rate'                                 AS relation,
    'delta'                                         AS measure,
    'float'                                         AS kind,
    '%'                                             AS unit,
    '7d'                                            AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM currency
WHERE
    type = 'delta'
    AND period = '7d'
    AND unit = '%'
UNION ALL
SELECT
    'currency/rate'                                 AS relation,
    'delta'                                         AS measure,
    'float'                                         AS kind,
    '%'                                             AS unit,
    '30d'                                           AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM currency
WHERE
    type = 'delta'
    AND period = '30d'
    AND unit = '%'
UNION ALL
SELECT
    'currency/rate'                                 AS relation,
    'delta'                                         AS measure,
    'float'                                         AS kind,
    '%'                                             AS unit,
    '365d'                                          AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM currency
WHERE
    type = 'delta'
    AND period = '365d'
    AND unit = '%'
UNION ALL
SELECT
    '-'                        AS relation,
    type                       AS measure,
    '-'                        AS kind,
    unit,
    period,
    '-'                        AS persisted,
    'yes'                      AS observed,
    CAST(count(*) AS VARCHAR)  AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM currency
WHERE
    type NOT IN ('delta', 'snapshot')
GROUP BY type, unit, period
UNION ALL
SELECT
    'equity/ticker'                                 AS relation,
    'market-volume-spot'                            AS measure,
    'float'                                         AS kind,
    '$'                                             AS unit,
    '1d'                                            AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM equity
WHERE
    type = 'market-volume-spot'
    AND period = '1d'
    AND unit = '$'
UNION ALL
SELECT
    'equity/ticker'                                 AS relation,
    'price-close'                                   AS measure,
    'float'                                         AS kind,
    '$'                                             AS unit,
    '1d'                                            AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM equity
WHERE
    type = 'price-close'
    AND period = '1d'
    AND unit = '$'
UNION ALL
SELECT
    'equity/ticker'                                 AS relation,
    'price-close-base'                              AS measure,
    'float'                                         AS kind,
    '$'                                             AS unit,
    '1d'                                            AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM equity
WHERE
    type = 'price-close-base'
    AND period = '1d'
    AND unit = '$'
UNION ALL
SELECT
    'equity/ticker'                                 AS relation,
    'price-close-spot'                              AS measure,
    'float'                                         AS kind,
    '$'                                             AS unit,
    '1d'                                            AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM equity
WHERE
    type = 'price-close-spot'
    AND period = '1d'
    AND unit = '$'
UNION ALL
SELECT
    'equity/ticker'                                 AS relation,
    'price-close-1d-change-percentage'              AS measure,
    'float'                                         AS kind,
    '%'                                             AS unit,
    '1d'                                            AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM equity
WHERE
    type = 'price-close-1d-change-percentage'
    AND period = '1d'
    AND unit = '%'
UNION ALL
SELECT
    'equity/ticker'                                 AS relation,
    'price-close-base-1d-change-percentage'         AS measure,
    'float'                                         AS kind,
    '%'                                             AS unit,
    '1d'                                            AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM equity
WHERE
    type = 'price-close-base-1d-change-percentage'
    AND period = '1d'
    AND unit = '%'
UNION ALL
SELECT
    'equity/ticker'                                 AS relation,
    'price-close-spot-1d-change-percentage'         AS measure,
    'float'                                         AS kind,
    '%'                                             AS unit,
    '1d'                                            AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM equity
WHERE
    type = 'price-close-spot-1d-change-percentage'
    AND period = '1d'
    AND unit = '%'
UNION ALL
SELECT
    'equity/ticker'                                 AS relation,
    'price-close-30d-change-percentage'             AS measure,
    'float'                                         AS kind,
    '%'                                             AS unit,
    '30d'                                           AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM equity
WHERE
    type = 'price-close-30d-change-percentage'
    AND period = '30d'
    AND unit = '%'
UNION ALL
SELECT
    'equity/ticker'                                 AS relation,
    'price-close-base-30d-change-percentage'        AS measure,
    'float'                                         AS kind,
    '%'                                             AS unit,
    '30d'                                           AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM equity
WHERE
    type = 'price-close-base-30d-change-percentage'
    AND period = '30d'
    AND unit = '%'
UNION ALL
SELECT
    'equity/ticker'                                 AS relation,
    'price-close-spot-30d-change-percentage'        AS measure,
    'float'                                         AS kind,
    '%'                                             AS unit,
    '30d'                                           AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM equity
WHERE
    type = 'price-close-spot-30d-change-percentage'
    AND period = '30d'
    AND unit = '%'
UNION ALL
SELECT
    'equity/ticker'                                 AS relation,
    'price-close-90d-change-percentage'             AS measure,
    'float'                                         AS kind,
    '%'                                             AS unit,
    '90d'                                           AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM equity
WHERE
    type = 'price-close-90d-change-percentage'
    AND period = '90d'
    AND unit = '%'
UNION ALL
SELECT
    'equity/ticker'                                 AS relation,
    'price-close-base-90d-change-percentage'        AS measure,
    'float'                                         AS kind,
    '%'                                             AS unit,
    '90d'                                           AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM equity
WHERE
    type = 'price-close-base-90d-change-percentage'
    AND period = '90d'
    AND unit = '%'
UNION ALL
SELECT
    'equity/ticker'                                 AS relation,
    'price-close-spot-90d-change-percentage'        AS measure,
    'float'                                         AS kind,
    '%'                                             AS unit,
    '90d'                                           AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM equity
WHERE
    type = 'price-close-spot-90d-change-percentage'
    AND period = '90d'
    AND unit = '%'
UNION ALL
SELECT
    'equity/ticker'                                 AS relation,
    'price-close-365d-change-percentage'            AS measure,
    'float'                                         AS kind,
    '%'                                             AS unit,
    '365d'                                          AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM equity
WHERE
    type = 'price-close-365d-change-percentage'
    AND period = '365d'
    AND unit = '%'
UNION ALL
SELECT
    'equity/ticker'                                 AS relation,
    'price-close-base-365d-change-percentage'       AS measure,
    'float'                                         AS kind,
    '%'                                             AS unit,
    '365d'                                          AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM equity
WHERE
    type = 'price-close-base-365d-change-percentage'
    AND period = '365d'
    AND unit = '%'
UNION ALL
SELECT
    'equity/ticker'                                 AS relation,
    'price-close-spot-365d-change-percentage'       AS measure,
    'float'                                         AS kind,
    '%'                                             AS unit,
    '365d'                                          AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM equity
WHERE
    type = 'price-close-spot-365d-change-percentage'
    AND period = '365d'
    AND unit = '%'
UNION ALL
SELECT
    '-'                        AS relation,
    type                       AS measure,
    '-'                        AS kind,
    unit,
    period,
    '-'                        AS persisted,
    'yes'                      AS observed,
    CAST(count(*) AS VARCHAR)  AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM equity
WHERE
    type NOT IN (
        'market-volume-spot', 'price-close', 'price-close-1d-change-percentage',
        'price-close-30d-change-percentage', 'price-close-365d-change-percentage',
        'price-close-90d-change-percentage', 'price-close-base',
        'price-close-base-1d-change-percentage', 'price-close-base-30d-change-percentage',
        'price-close-base-365d-change-percentage', 'price-close-base-90d-change-percentage',
        'price-close-spot', 'price-close-spot-1d-change-percentage',
        'price-close-spot-30d-change-percentage', 'price-close-spot-365d-change-percentage',
        'price-close-spot-90d-change-percentage'
    )
GROUP BY type, unit, period
UNION ALL
SELECT
    'interest/rate'                                 AS relation,
    'mean'                                          AS measure,
    'float'                                         AS kind,
    '%'                                             AS unit,
    '1mo'                                           AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM interest
WHERE
    type = 'mean'
    AND period = '1mo'
    AND unit = '%'
UNION ALL
SELECT
    'interest/rate'                                 AS relation,
    'mean'                                          AS measure,
    'float'                                         AS kind,
    '%'                                             AS unit,
    '1y'                                            AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM interest
WHERE
    type = 'mean'
    AND period = '1y'
    AND unit = '%'
UNION ALL
SELECT
    'interest/rate'                                 AS relation,
    'mean'                                          AS measure,
    'float'                                         AS kind,
    '%'                                             AS unit,
    '5y'                                            AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM interest
WHERE
    type = 'mean'
    AND period = '5y'
    AND unit = '%'
UNION ALL
SELECT
    'interest/rate'                                 AS relation,
    'mean'                                          AS measure,
    'float'                                         AS kind,
    '%'                                             AS unit,
    '10y'                                           AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM interest
WHERE
    type = 'mean'
    AND period = '10y'
    AND unit = '%'
UNION ALL
SELECT
    'interest/rate'                                 AS relation,
    'mean'                                          AS measure,
    'float'                                         AS kind,
    '%'                                             AS unit,
    '20y'                                           AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM interest
WHERE
    type = 'mean'
    AND period = '20y'
    AND unit = '%'
UNION ALL
SELECT
    'interest/rate'                                 AS relation,
    'mean'                                          AS measure,
    'float'                                         AS kind,
    '%'                                             AS unit,
    '40y'                                           AS period,
    'yes'                                           AS persisted,
    CASE WHEN count(*) > 0 THEN 'yes' ELSE 'no' END AS observed,
    CAST(count(*) AS VARCHAR)                       AS rows,
    CAST(min(time) AS VARCHAR)                      AS oldest,
    CAST(max(time) AS VARCHAR)                      AS newest
FROM interest
WHERE
    type = 'mean'
    AND period = '40y'
    AND unit = '%'
UNION ALL
SELECT
    '-'                        AS relation,
    type                       AS measure,
    '-'                        AS kind,
    unit,
    period,
    '-'                        AS persisted,
    'yes'                      AS observed,
    CAST(count(*) AS VARCHAR)  AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM interest
WHERE
    type NOT IN ('mean')
GROUP BY type, unit, period
ORDER BY relation, measure, unit, period;

-- entities
SELECT
    'currency/rate'                                                                AS relation,
    'entity*'                                                                      AS dimension,
    entity,
    CASE WHEN entity IN ('AUD/USD', 'AUD/GBP', 'AUD/SGD') THEN 'yes' ELSE 'no' END AS declared,
    count(*)                                                                       AS rows,
    min(time)                                                                      AS oldest,
    max(time)                                                                      AS newest
FROM currency
WHERE
    type IN ('delta', 'snapshot')
GROUP BY entity, CASE WHEN entity IN ('AUD/USD', 'AUD/GBP', 'AUD/SGD') THEN 'yes' ELSE 'no' END
UNION ALL
SELECT
    'interest/rate'                                                           AS relation,
    'entity*'                                                                 AS dimension,
    entity,
    CASE WHEN entity IN ('Bank', 'Inflation', 'Net') THEN 'yes' ELSE 'no' END AS declared,
    count(*)                                                                  AS rows,
    min(time)                                                                 AS oldest,
    max(time)                                                                 AS newest
FROM interest
WHERE
    type IN ('mean')
GROUP BY entity, CASE WHEN entity IN ('Bank', 'Inflation', 'Net') THEN 'yes' ELSE 'no' END
UNION ALL
SELECT
    'equity/ticker' AS relation,
    'entity*'       AS dimension,
    entity,
    '-'             AS declared,
    count(*)        AS rows,
    min(time)       AS oldest,
    max(time)       AS newest
FROM equity
WHERE
    type IN (
        'market-volume-spot', 'price-close', 'price-close-1d-change-percentage',
        'price-close-30d-change-percentage', 'price-close-365d-change-percentage',
        'price-close-90d-change-percentage', 'price-close-base',
        'price-close-base-1d-change-percentage', 'price-close-base-30d-change-percentage',
        'price-close-base-365d-change-percentage', 'price-close-base-90d-change-percentage',
        'price-close-spot', 'price-close-spot-1d-change-percentage',
        'price-close-spot-30d-change-percentage', 'price-close-spot-365d-change-percentage',
        'price-close-spot-90d-change-percentage'
    )
GROUP BY entity
ORDER BY relation, entity;
