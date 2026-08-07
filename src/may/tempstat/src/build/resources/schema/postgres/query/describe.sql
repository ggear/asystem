--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- dimensions
SELECT
    'tempstat/device' AS relation,
    'device*'         AS dimension,
    2                 AS measures,
    '15m'             AS cadence,
    count(*)          AS rows,
    min(time)         AS oldest,
    max(time)         AS newest
FROM tempstat
WHERE
    type IN ('period_ms', 'sensors_failed')
UNION ALL
SELECT
    'tempstat/sensor' AS relation,
    'sensor*'         AS dimension,
    1                 AS measures,
    '15m'             AS cadence,
    count(*)          AS rows,
    min(time)         AS oldest,
    max(time)         AS newest
FROM tempstat
WHERE
    type IN ('temperature_celsius')
ORDER BY rows DESC;

-- measures
SELECT
    'tempstat/device'          AS relation,
    'period_ms'                AS measure,
    'int'                      AS kind,
    'milliseconds'             AS unit,
    '15m'                      AS period,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM tempstat
WHERE
    type = 'period_ms'
    AND period = '15m'
    AND unit = 'milliseconds'
UNION ALL
SELECT
    'tempstat/device'          AS relation,
    'sensors_failed'           AS measure,
    'int'                      AS kind,
    'count'                    AS unit,
    '15m'                      AS period,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM tempstat
WHERE
    type = 'sensors_failed'
    AND period = '15m'
    AND unit = 'count'
UNION ALL
SELECT
    'tempstat/sensor'          AS relation,
    'temperature_celsius'      AS measure,
    'float'                    AS kind,
    'celsius'                  AS unit,
    '15m'                      AS period,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM tempstat
WHERE
    type = 'temperature_celsius'
    AND period = '15m'
    AND unit = 'celsius'
UNION ALL
SELECT
    '-'                        AS relation,
    type                       AS measure,
    '-'                        AS kind,
    unit,
    period,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM tempstat
WHERE
    type NOT IN ('period_ms', 'sensors_failed', 'temperature_celsius')
GROUP BY type, unit, period
ORDER BY rows DESC NULLS LAST;

-- entities
SELECT
    'tempstat/device'                                         AS relation,
    'device*'                                                 AS dimension,
    entity,
    CASE WHEN entity IN ('tempstat') THEN 'yes' ELSE 'no' END AS declared,
    count(*)                                                  AS rows,
    min(time)                                                 AS oldest,
    max(time)                                                 AS newest
FROM tempstat
WHERE
    type IN ('period_ms', 'sensors_failed')
GROUP BY entity, CASE WHEN entity IN ('tempstat') THEN 'yes' ELSE 'no' END
UNION ALL
SELECT
    'tempstat/sensor'                                                                                                       AS relation,
    'sensor*'                                                                                                               AS dimension,
    entity,
    CASE WHEN entity IN ('utility_temperature', 'rack_top_temperature', 'rack_bottom_temperature') THEN 'yes' ELSE 'no' END AS declared,
    count(*)                                                                                                                AS rows,
    min(time)                                                                                                               AS oldest,
    max(time)                                                                                                               AS newest
FROM tempstat
WHERE
    type IN ('temperature_celsius')
GROUP BY entity, CASE WHEN entity IN ('utility_temperature', 'rack_top_temperature', 'rack_bottom_temperature') THEN 'yes' ELSE 'no' END
ORDER BY rows DESC;
