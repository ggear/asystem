--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- dimensions
SELECT
    'sensor'                         AS relation,
    'entity_id/unit_of_measurement*' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__current'                AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__current
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__energy'                 AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    4                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__energy
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__humidity'               AS relation,
    'entity_id/unit_of_measurement*' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__humidity
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__power'                  AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__power
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__temperature'            AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__temperature
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__voltage'                AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__voltage
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'switch'                   AS relation,
    'entity_id*'               AS dimension,
    10                         AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM switch
WHERE
    module = 'homeassistant'
ORDER BY rows DESC;

-- measures
SELECT
    'sensor'                                                    AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    '-'                   AS relation,
    column_name           AS measure,
    '-'                   AS kind,
    '-'                   AS unit,
    '-'                   AS period,
    CAST(NULL AS BIGINT)  AS rows,
    CAST(NULL AS VARCHAR) AS oldest,
    CAST(NULL AS VARCHAR) AS newest
FROM information_schema.columns
WHERE
    table_name = 'sensor'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'sensor__current'                                           AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__current
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    '-'                   AS relation,
    column_name           AS measure,
    '-'                   AS kind,
    '-'                   AS unit,
    '-'                   AS period,
    CAST(NULL AS BIGINT)  AS rows,
    CAST(NULL AS VARCHAR) AS oldest,
    CAST(NULL AS VARCHAR) AS newest
FROM information_schema.columns
WHERE
    table_name = 'sensor__current'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'sensor__energy'                                                       AS relation,
    'last_valid_state'                                                     AS measure,
    'float'                                                                AS kind,
    '-'                                                                    AS unit,
    '<on-change>'                                                          AS period,
    count(last_valid_state)                                                AS rows,
    CAST(min(time) FILTER (WHERE last_valid_state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE last_valid_state IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__energy
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__energy'                                                 AS relation,
    'next_reset'                                                     AS measure,
    'float'                                                          AS kind,
    '-'                                                              AS unit,
    '<on-change>'                                                    AS period,
    count(next_reset)                                                AS rows,
    CAST(min(time) FILTER (WHERE next_reset IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE next_reset IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__energy
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__energy'                                            AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__energy
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    '-'                   AS relation,
    column_name           AS measure,
    '-'                   AS kind,
    '-'                   AS unit,
    '-'                   AS period,
    CAST(NULL AS BIGINT)  AS rows,
    CAST(NULL AS VARCHAR) AS oldest,
    CAST(NULL AS VARCHAR) AS newest
FROM information_schema.columns
WHERE
    table_name = 'sensor__energy'
    AND column_name NOT IN (
        'entity_id', 'last_valid_state', 'module', 'next_reset', 'next_reset_str', 'time',
        'unit_of_measurement', 'value'
    )
UNION ALL
SELECT
    'sensor__humidity'                                          AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__humidity
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    '-'                   AS relation,
    column_name           AS measure,
    '-'                   AS kind,
    '-'                   AS unit,
    '-'                   AS period,
    CAST(NULL AS BIGINT)  AS rows,
    CAST(NULL AS VARCHAR) AS oldest,
    CAST(NULL AS VARCHAR) AS newest
FROM information_schema.columns
WHERE
    table_name = 'sensor__humidity'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'sensor__power'                                             AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__power
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    '-'                   AS relation,
    column_name           AS measure,
    '-'                   AS kind,
    '-'                   AS unit,
    '-'                   AS period,
    CAST(NULL AS BIGINT)  AS rows,
    CAST(NULL AS VARCHAR) AS oldest,
    CAST(NULL AS VARCHAR) AS newest
FROM information_schema.columns
WHERE
    table_name = 'sensor__power'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'sensor__temperature'                                       AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__temperature
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    '-'                   AS relation,
    column_name           AS measure,
    '-'                   AS kind,
    '-'                   AS unit,
    '-'                   AS period,
    CAST(NULL AS BIGINT)  AS rows,
    CAST(NULL AS VARCHAR) AS oldest,
    CAST(NULL AS VARCHAR) AS newest
FROM information_schema.columns
WHERE
    table_name = 'sensor__temperature'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    '-'                   AS relation,
    column_name           AS measure,
    '-'                   AS kind,
    '-'                   AS unit,
    '-'                   AS period,
    CAST(NULL AS BIGINT)  AS rows,
    CAST(NULL AS VARCHAR) AS oldest,
    CAST(NULL AS VARCHAR) AS newest
FROM information_schema.columns
WHERE
    table_name = 'sensor__timestamp'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time')
UNION ALL
SELECT
    'sensor__voltage'                                           AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__voltage
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    '-'                   AS relation,
    column_name           AS measure,
    '-'                   AS kind,
    '-'                   AS unit,
    '-'                   AS period,
    CAST(NULL AS BIGINT)  AS rows,
    CAST(NULL AS VARCHAR) AS oldest,
    CAST(NULL AS VARCHAR) AS newest
FROM information_schema.columns
WHERE
    table_name = 'sensor__voltage'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'switch'                                                            AS relation,
    'assumed_state'                                                     AS measure,
    'float'                                                             AS kind,
    '-'                                                                 AS unit,
    '<on-change>'                                                       AS period,
    count(assumed_state)                                                AS rows,
    CAST(min(time) FILTER (WHERE assumed_state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE assumed_state IS NOT NULL) AS VARCHAR) AS newest
FROM switch
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'switch'                                                             AS relation,
    'brightness_pct'                                                     AS measure,
    'float'                                                              AS kind,
    '-'                                                                  AS unit,
    '<on-change>'                                                        AS period,
    count(brightness_pct)                                                AS rows,
    CAST(min(time) FILTER (WHERE brightness_pct IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE brightness_pct IS NOT NULL) AS VARCHAR) AS newest
FROM switch
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'switch'                                                              AS relation,
    'force_rgb_color'                                                     AS measure,
    'float'                                                               AS kind,
    '-'                                                                   AS unit,
    '<on-change>'                                                         AS period,
    count(force_rgb_color)                                                AS rows,
    CAST(min(time) FILTER (WHERE force_rgb_color IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE force_rgb_color IS NOT NULL) AS VARCHAR) AS newest
FROM switch
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'switch'                                                        AS relation,
    'rgb_color'                                                     AS measure,
    'float'                                                         AS kind,
    '-'                                                             AS unit,
    '<on-change>'                                                   AS period,
    count(rgb_color)                                                AS rows,
    CAST(min(time) FILTER (WHERE rgb_color IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE rgb_color IS NOT NULL) AS VARCHAR) AS newest
FROM switch
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'switch'                                                           AS relation,
    'sun_position'                                                     AS measure,
    'float'                                                            AS kind,
    '-'                                                                AS unit,
    '<on-change>'                                                      AS period,
    count(sun_position)                                                AS rows,
    CAST(min(time) FILTER (WHERE sun_position IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE sun_position IS NOT NULL) AS VARCHAR) AS newest
FROM switch
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'switch'                                                    AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM switch
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    '-'                   AS relation,
    column_name           AS measure,
    '-'                   AS kind,
    '-'                   AS unit,
    '-'                   AS period,
    CAST(NULL AS BIGINT)  AS rows,
    CAST(NULL AS VARCHAR) AS oldest,
    CAST(NULL AS VARCHAR) AS newest
FROM information_schema.columns
WHERE
    table_name = 'switch'
    AND column_name NOT IN (
        'assumed_state', 'autoreset_time_remaining_str', 'brightness_pct',
        'configuration_str', 'entity_id', 'force_rgb_color', 'module', 'rgb_color',
        'rgb_color_str', 'state', 'sun_position', 'time', 'value'
    )
ORDER BY rows DESC NULLS LAST;

-- entities
SELECT
    'sensor'                                    AS relation,
    'entity_id/unit_of_measurement*'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__current'                           AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__current
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__energy'                            AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__energy
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__humidity'                          AS relation,
    'entity_id/unit_of_measurement*'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__humidity
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__power'                             AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__power
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__temperature'                       AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__temperature
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__voltage'                           AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__voltage
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'switch'                   AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM switch
WHERE
    module = 'homeassistant'
GROUP BY entity_id
ORDER BY rows DESC;
