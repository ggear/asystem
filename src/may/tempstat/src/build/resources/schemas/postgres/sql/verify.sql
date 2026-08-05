--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- declared vocabulary against what the service actually wrote, rows come back only on drift
SELECT
    'tempstat'                                                    AS relation,
    coalesce(d.type, o.type)                                      AS type,
    coalesce(d.period, o.period)                                  AS period,
    coalesce(d.unit, o.unit)                                      AS unit,
    CASE WHEN d.type IS NULL THEN 'undeclared' ELSE 'missing' END AS fault
FROM (VALUES
    ('period_ms', '15m', 'milliseconds'),
    ('sensors_failed', '15m', 'count'),
    ('temperature_celsius', '15m', 'celsius')
) AS d(type, period, unit)
FULL OUTER JOIN (SELECT DISTINCT type, period, unit FROM tempstat) AS o
    ON d.type = o.type AND d.period = o.period AND d.unit = o.unit
WHERE
    d.type IS NULL OR o.type IS NULL;

SELECT
    'tempstat'   AS relation,
    entity,
    count(*)     AS rows_total,
    'undeclared' AS fault
FROM tempstat
WHERE
    entity NOT IN ('rack_bottom_temperature', 'rack_top_temperature', 'tempstat', 'utility_temperature')
GROUP BY entity;
