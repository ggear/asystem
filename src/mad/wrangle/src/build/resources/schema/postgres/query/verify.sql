--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- declared vocabulary against what the service actually wrote, rows come back only on drift
SELECT
    coalesce(d.relation, 'currency')                              AS relation,
    coalesce(d.type, o.type)                                      AS measure,
    coalesce(d.period, o.period)                                  AS period,
    coalesce(d.unit, o.unit)                                      AS unit,
    CASE WHEN d.type IS NULL THEN 'undeclared' ELSE 'missing' END AS fault
FROM (VALUES
    ('currency/rate', 'snapshot', '1d', '$'),
    ('currency/rate', 'delta', '1d', '%'),
    ('currency/rate', 'delta', '7d', '%'),
    ('currency/rate', 'delta', '30d', '%'),
    ('currency/rate', 'delta', '365d', '%')
) AS d(relation, type, period, unit)
FULL OUTER JOIN (SELECT DISTINCT type, period, unit FROM currency) AS o
    ON d.type = o.type AND d.period = o.period AND d.unit = o.unit
WHERE
    d.type IS NULL OR o.type IS NULL
ORDER BY fault, measure;

SELECT
    coalesce(d.relation, 'equity')                                AS relation,
    coalesce(d.type, o.type)                                      AS measure,
    coalesce(d.period, o.period)                                  AS period,
    coalesce(d.unit, o.unit)                                      AS unit,
    CASE WHEN d.type IS NULL THEN 'undeclared' ELSE 'missing' END AS fault
FROM (VALUES
    ('equity/ticker', 'market-volume-spot', '1d', '$'),
    ('equity/ticker', 'price-close', '1d', '$'),
    ('equity/ticker', 'price-close-base', '1d', '$'),
    ('equity/ticker', 'price-close-spot', '1d', '$'),
    ('equity/ticker', 'price-close-1d-change-percentage', '1d', '%'),
    ('equity/ticker', 'price-close-base-1d-change-percentage', '1d', '%'),
    ('equity/ticker', 'price-close-spot-1d-change-percentage', '1d', '%'),
    ('equity/ticker', 'price-close-30d-change-percentage', '30d', '%'),
    ('equity/ticker', 'price-close-base-30d-change-percentage', '30d', '%'),
    ('equity/ticker', 'price-close-spot-30d-change-percentage', '30d', '%'),
    ('equity/ticker', 'price-close-90d-change-percentage', '90d', '%'),
    ('equity/ticker', 'price-close-base-90d-change-percentage', '90d', '%'),
    ('equity/ticker', 'price-close-spot-90d-change-percentage', '90d', '%'),
    ('equity/ticker', 'price-close-365d-change-percentage', '365d', '%'),
    ('equity/ticker', 'price-close-base-365d-change-percentage', '365d', '%'),
    ('equity/ticker', 'price-close-spot-365d-change-percentage', '365d', '%')
) AS d(relation, type, period, unit)
FULL OUTER JOIN (SELECT DISTINCT type, period, unit FROM equity) AS o
    ON d.type = o.type AND d.period = o.period AND d.unit = o.unit
WHERE
    d.type IS NULL OR o.type IS NULL
ORDER BY fault, measure;

SELECT
    coalesce(d.relation, 'interest')                              AS relation,
    coalesce(d.type, o.type)                                      AS measure,
    coalesce(d.period, o.period)                                  AS period,
    coalesce(d.unit, o.unit)                                      AS unit,
    CASE WHEN d.type IS NULL THEN 'undeclared' ELSE 'missing' END AS fault
FROM (VALUES
    ('interest/rate', 'mean', '1mo', '%'),
    ('interest/rate', 'mean', '1y', '%'),
    ('interest/rate', 'mean', '5y', '%'),
    ('interest/rate', 'mean', '10y', '%'),
    ('interest/rate', 'mean', '20y', '%'),
    ('interest/rate', 'mean', '40y', '%')
) AS d(relation, type, period, unit)
FULL OUTER JOIN (SELECT DISTINCT type, period, unit FROM interest) AS o
    ON d.type = o.type AND d.period = o.period AND d.unit = o.unit
WHERE
    d.type IS NULL OR o.type IS NULL
ORDER BY fault, measure;
