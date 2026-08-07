--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- declared vocabulary against what the service actually wrote, rows come back only on drift
SELECT
    coalesce(d.relation, 'tempstat')                              AS relation,
    coalesce(d.type, o.type)                                      AS measure,
    coalesce(d.period, o.period)                                  AS period,
    coalesce(d.unit, o.unit)                                      AS unit,
    CASE WHEN d.type IS NULL THEN 'undeclared' ELSE 'missing' END AS fault
FROM (VALUES
    ('tempstat/device', 'period_ms', '15m', 'milliseconds'),
    ('tempstat/device', 'sensors_failed', '15m', 'count'),
    ('tempstat/sensor', 'temperature_celsius', '15m', 'celsius')
) AS d(relation, type, period, unit)
FULL OUTER JOIN (SELECT DISTINCT type, period, unit FROM tempstat) AS o
    ON d.type = o.type AND d.period = o.period AND d.unit = o.unit
WHERE
    d.type IS NULL OR o.type IS NULL
ORDER BY fault, measure;
