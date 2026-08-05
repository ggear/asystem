--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- declared vocabulary against what the service actually wrote, rows come back only on drift
SELECT
    'currency'                                                    AS relation,
    coalesce(d.type, o.type)                                      AS type,
    coalesce(d.period, o.period)                                  AS period,
    coalesce(d.unit, o.unit)                                      AS unit,
    CASE WHEN d.type IS NULL THEN 'undeclared' ELSE 'missing' END AS fault
FROM (VALUES
    ('snapshot', '1d', '$'),
    ('delta', '1d', '%'),
    ('delta', '7d', '%'),
    ('delta', '30d', '%'),
    ('delta', '365d', '%')
) AS d(type, period, unit)
FULL OUTER JOIN (SELECT DISTINCT type, period, unit FROM currency) AS o
    ON d.type = o.type AND d.period = o.period AND d.unit = o.unit
WHERE
    d.type IS NULL OR o.type IS NULL;

SELECT
    'currency'   AS relation,
    entity,
    count(*)     AS rows_total,
    'undeclared' AS fault
FROM currency
WHERE
    entity NOT IN ('AUD/GBP', 'AUD/SGD', 'AUD/USD')
GROUP BY entity;

SELECT
    'equity'                                                      AS relation,
    coalesce(d.type, o.type)                                      AS type,
    coalesce(d.period, o.period)                                  AS period,
    coalesce(d.unit, o.unit)                                      AS unit,
    CASE WHEN d.type IS NULL THEN 'undeclared' ELSE 'missing' END AS fault
FROM (VALUES
    ('market-volume-spot', '1d', '$'),
    ('price-close', '1d', '$'),
    ('price-close-base', '1d', '$'),
    ('price-close-spot', '1d', '$'),
    ('price-close-1d-change-percentage', '1d', '%'),
    ('price-close-base-1d-change-percentage', '1d', '%'),
    ('price-close-spot-1d-change-percentage', '1d', '%'),
    ('price-close-30d-change-percentage', '30d', '%'),
    ('price-close-base-30d-change-percentage', '30d', '%'),
    ('price-close-spot-30d-change-percentage', '30d', '%'),
    ('price-close-90d-change-percentage', '90d', '%'),
    ('price-close-base-90d-change-percentage', '90d', '%'),
    ('price-close-spot-90d-change-percentage', '90d', '%'),
    ('price-close-365d-change-percentage', '365d', '%'),
    ('price-close-base-365d-change-percentage', '365d', '%'),
    ('price-close-spot-365d-change-percentage', '365d', '%')
) AS d(type, period, unit)
FULL OUTER JOIN (SELECT DISTINCT type, period, unit FROM equity) AS o
    ON d.type = o.type AND d.period = o.period AND d.unit = o.unit
WHERE
    d.type IS NULL OR o.type IS NULL;

SELECT
    'interest'                                                    AS relation,
    coalesce(d.type, o.type)                                      AS type,
    coalesce(d.period, o.period)                                  AS period,
    coalesce(d.unit, o.unit)                                      AS unit,
    CASE WHEN d.type IS NULL THEN 'undeclared' ELSE 'missing' END AS fault
FROM (VALUES
    ('mean', '1mo', '%'),
    ('mean', '1y', '%'),
    ('mean', '5y', '%'),
    ('mean', '10y', '%'),
    ('mean', '20y', '%'),
    ('mean', '40y', '%')
) AS d(type, period, unit)
FULL OUTER JOIN (SELECT DISTINCT type, period, unit FROM interest) AS o
    ON d.type = o.type AND d.period = o.period AND d.unit = o.unit
WHERE
    d.type IS NULL OR o.type IS NULL;

SELECT
    'interest'   AS relation,
    entity,
    count(*)     AS rows_total,
    'undeclared' AS fault
FROM interest
WHERE
    entity NOT IN ('Bank', 'Inflation', 'Net')
GROUP BY entity;
