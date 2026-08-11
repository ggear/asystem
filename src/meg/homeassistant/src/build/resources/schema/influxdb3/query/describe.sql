--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- dimensions
SELECT
    'automation'               AS relation,
    'entity_id*'               AS dimension,
    5                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM automation
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor'            AS relation,
    'entity_id*'               AS dimension,
    2                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM binary_sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor__battery'   AS relation,
    'entity_id*'               AS dimension,
    2                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM binary_sensor__battery
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor__battery_charging' AS relation,
    'entity_id*'                      AS dimension,
    2                                 AS measures,
    '<on-change>'                     AS cadence,
    count(*)                          AS rows,
    CAST(min(time) AS VARCHAR)        AS oldest,
    CAST(max(time) AS VARCHAR)        AS newest
FROM binary_sensor__battery_charging
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor__connectivity' AS relation,
    'entity_id*'                  AS dimension,
    4                             AS measures,
    '<on-change>'                 AS cadence,
    count(*)                      AS rows,
    CAST(min(time) AS VARCHAR)    AS oldest,
    CAST(max(time) AS VARCHAR)    AS newest
FROM binary_sensor__connectivity
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor__door'      AS relation,
    'entity_id*'               AS dimension,
    2                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM binary_sensor__door
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor__occupancy' AS relation,
    'entity_id*'               AS dimension,
    2                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM binary_sensor__occupancy
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor__safety'    AS relation,
    'entity_id*'               AS dimension,
    2                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM binary_sensor__safety
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'calendar'                 AS relation,
    'entity_id*'               AS dimension,
    10                         AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM calendar
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'climate'                  AS relation,
    'entity_id*'               AS dimension,
    7                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM climate
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'device_tracker'           AS relation,
    'entity_id*'               AS dimension,
    11                         AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM device_tracker
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'fan'                      AS relation,
    'entity_id*'               AS dimension,
    5                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM fan
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'input_boolean'            AS relation,
    'entity_id*'               AS dimension,
    2                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM input_boolean
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'light'                    AS relation,
    'entity_id*'               AS dimension,
    12                         AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM light
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'lock'                     AS relation,
    'entity_id*'               AS dimension,
    2                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM lock
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'media_player'             AS relation,
    'entity_id*'               AS dimension,
    2                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM media_player
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'media_player__speaker'    AS relation,
    'entity_id*'               AS dimension,
    14                         AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM media_player__speaker
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'media_player__tv'         AS relation,
    'entity_id*'               AS dimension,
    2                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM media_player__tv
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'number'                         AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    4                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM number
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'person'                   AS relation,
    'entity_id*'               AS dimension,
    7                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM person
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                         AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    78                               AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__atmospheric_pressure'   AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    3                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__atmospheric_pressure
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__battery'                AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    3                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__battery
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__carbon_dioxide'         AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    3                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__carbon_dioxide
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
    'sensor__enum'             AS relation,
    'entity_id*'               AS dimension,
    4                          AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM sensor__enum
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__humidity'               AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    13                               AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__humidity
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__pm25'                   AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__pm25
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__power'                  AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    2                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__power
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__precipitation'          AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    12                               AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__precipitation
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__pressure'               AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__pressure
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__signal_strength'        AS relation,
    'entity_id/unit_of_measurement*' AS dimension,
    1                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__signal_strength
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__sound_pressure'         AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    3                                AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__sound_pressure
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__temperature'            AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    21                               AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__temperature
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__timestamp'        AS relation,
    'entity_id*'               AS dimension,
    12                         AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM sensor__timestamp
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
    'sensor__wind_speed'             AS relation,
    'entity_id*/unit_of_measurement' AS dimension,
    11                               AS measures,
    '<on-change>'                    AS cadence,
    count(*)                         AS rows,
    CAST(min(time) AS VARCHAR)       AS oldest,
    CAST(max(time) AS VARCHAR)       AS newest
FROM sensor__wind_speed
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sun'                      AS relation,
    'entity_id*'               AS dimension,
    13                         AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM sun
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'switch'                   AS relation,
    'entity_id*'               AS dimension,
    13                         AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM switch
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'update__firmware'         AS relation,
    'entity_id*'               AS dimension,
    13                         AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM update__firmware
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'weather'                  AS relation,
    'entity_id*'               AS dimension,
    33                         AS measures,
    '<on-change>'              AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM weather
WHERE
    module = 'homeassistant'
ORDER BY rows DESC;

-- measures
SELECT
    'automation'                                                         AS relation,
    'last_triggered'                                                     AS measure,
    'float'                                                              AS kind,
    '-'                                                                  AS unit,
    '<on-change>'                                                        AS period,
    count(last_triggered)                                                AS rows,
    CAST(min(time) FILTER (WHERE last_triggered IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE last_triggered IS NOT NULL) AS VARCHAR) AS newest
FROM automation
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'automation'                                              AS relation,
    'max'                                                     AS measure,
    'float'                                                   AS kind,
    '-'                                                       AS unit,
    '<on-change>'                                             AS period,
    count(max)                                                AS rows,
    CAST(min(time) FILTER (WHERE max IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE max IS NOT NULL) AS VARCHAR) AS newest
FROM automation
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'automation'                                                AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM automation
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
    table_name = 'automation'
    AND column_name NOT IN (
        'entity_id', 'last_triggered', 'last_triggered_str', 'max', 'module', 'state',
        'time', 'value'
    )
UNION ALL
SELECT
    'binary_sensor'                                             AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor
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
    table_name = 'binary_sensor'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'binary_sensor__battery'                                    AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor__battery
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
    table_name = 'binary_sensor__battery'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'binary_sensor__battery_charging'                           AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor__battery_charging
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
    table_name = 'binary_sensor__battery_charging'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'binary_sensor__connectivity'                                  AS relation,
    'latitude'                                                     AS measure,
    'float'                                                        AS kind,
    '-'                                                            AS unit,
    '<on-change>'                                                  AS period,
    count(latitude)                                                AS rows,
    CAST(min(time) FILTER (WHERE latitude IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE latitude IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor__connectivity
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor__connectivity'                                   AS relation,
    'longitude'                                                     AS measure,
    'float'                                                         AS kind,
    '-'                                                             AS unit,
    '<on-change>'                                                   AS period,
    count(longitude)                                                AS rows,
    CAST(min(time) FILTER (WHERE longitude IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE longitude IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor__connectivity
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'binary_sensor__connectivity'                               AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor__connectivity
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
    table_name = 'binary_sensor__connectivity'
    AND column_name NOT IN ('entity_id', 'latitude', 'longitude', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'binary_sensor__door'                                       AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor__door
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
    table_name = 'binary_sensor__door'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'binary_sensor__occupancy'                                  AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor__occupancy
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
    table_name = 'binary_sensor__occupancy'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'binary_sensor__safety'                                     AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM binary_sensor__safety
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
    table_name = 'binary_sensor__safety'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'calendar'                                                    AS relation,
    'all_day'                                                     AS measure,
    'float'                                                       AS kind,
    '-'                                                           AS unit,
    '<on-change>'                                                 AS period,
    count(all_day)                                                AS rows,
    CAST(min(time) FILTER (WHERE all_day IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE all_day IS NOT NULL) AS VARCHAR) AS newest
FROM calendar
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'calendar'                                                     AS relation,
    'end_time'                                                     AS measure,
    'float'                                                        AS kind,
    '-'                                                            AS unit,
    '<on-change>'                                                  AS period,
    count(end_time)                                                AS rows,
    CAST(min(time) FILTER (WHERE end_time IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE end_time IS NOT NULL) AS VARCHAR) AS newest
FROM calendar
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'calendar'                                                       AS relation,
    'start_time'                                                     AS measure,
    'float'                                                          AS kind,
    '-'                                                              AS unit,
    '<on-change>'                                                    AS period,
    count(start_time)                                                AS rows,
    CAST(min(time) FILTER (WHERE start_time IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE start_time IS NOT NULL) AS VARCHAR) AS newest
FROM calendar
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'calendar'                                                  AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM calendar
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
    table_name = 'calendar'
    AND column_name NOT IN (
        'all_day', 'description_str', 'end_time', 'end_time_str', 'entity_id',
        'location_str', 'message_str', 'module', 'start_time', 'start_time_str', 'state',
        'time', 'value'
    )
UNION ALL
SELECT
    'climate'                                                                 AS relation,
    'current_temperature'                                                     AS measure,
    'float'                                                                   AS kind,
    '-'                                                                       AS unit,
    '<on-change>'                                                             AS period,
    count(current_temperature)                                                AS rows,
    CAST(min(time) FILTER (WHERE current_temperature IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE current_temperature IS NOT NULL) AS VARCHAR) AS newest
FROM climate
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'climate'                                                      AS relation,
    'max_temp'                                                     AS measure,
    'float'                                                        AS kind,
    '-'                                                            AS unit,
    '<on-change>'                                                  AS period,
    count(max_temp)                                                AS rows,
    CAST(min(time) FILTER (WHERE max_temp IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE max_temp IS NOT NULL) AS VARCHAR) AS newest
FROM climate
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'climate'                                                      AS relation,
    'min_temp'                                                     AS measure,
    'float'                                                        AS kind,
    '-'                                                            AS unit,
    '<on-change>'                                                  AS period,
    count(min_temp)                                                AS rows,
    CAST(min(time) FILTER (WHERE min_temp IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE min_temp IS NOT NULL) AS VARCHAR) AS newest
FROM climate
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'climate'                                                         AS relation,
    'temperature'                                                     AS measure,
    'float'                                                           AS kind,
    '-'                                                               AS unit,
    '<on-change>'                                                     AS period,
    count(temperature)                                                AS rows,
    CAST(min(time) FILTER (WHERE temperature IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE temperature IS NOT NULL) AS VARCHAR) AS newest
FROM climate
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
    table_name = 'climate'
    AND column_name NOT IN (
        'current_temperature', 'entity_id', 'hvac_action_str', 'hvac_modes_str', 'max_temp',
        'min_temp', 'module', 'state', 'temperature', 'time'
    )
UNION ALL
SELECT
    'device_tracker'                                               AS relation,
    'altitude'                                                     AS measure,
    'float'                                                        AS kind,
    '-'                                                            AS unit,
    '<on-change>'                                                  AS period,
    count(altitude)                                                AS rows,
    CAST(min(time) FILTER (WHERE altitude IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE altitude IS NOT NULL) AS VARCHAR) AS newest
FROM device_tracker
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'device_tracker'                                                    AS relation,
    'battery_level'                                                     AS measure,
    'float'                                                             AS kind,
    '-'                                                                 AS unit,
    '<on-change>'                                                       AS period,
    count(battery_level)                                                AS rows,
    CAST(min(time) FILTER (WHERE battery_level IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE battery_level IS NOT NULL) AS VARCHAR) AS newest
FROM device_tracker
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'device_tracker'                                                   AS relation,
    'gps_accuracy'                                                     AS measure,
    'float'                                                            AS kind,
    '-'                                                                AS unit,
    '<on-change>'                                                      AS period,
    count(gps_accuracy)                                                AS rows,
    CAST(min(time) FILTER (WHERE gps_accuracy IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE gps_accuracy IS NOT NULL) AS VARCHAR) AS newest
FROM device_tracker
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'device_tracker'                                               AS relation,
    'latitude'                                                     AS measure,
    'float'                                                        AS kind,
    '-'                                                            AS unit,
    '<on-change>'                                                  AS period,
    count(latitude)                                                AS rows,
    CAST(min(time) FILTER (WHERE latitude IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE latitude IS NOT NULL) AS VARCHAR) AS newest
FROM device_tracker
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'device_tracker'                                                AS relation,
    'longitude'                                                     AS measure,
    'float'                                                         AS kind,
    '-'                                                             AS unit,
    '<on-change>'                                                   AS period,
    count(longitude)                                                AS rows,
    CAST(min(time) FILTER (WHERE longitude IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE longitude IS NOT NULL) AS VARCHAR) AS newest
FROM device_tracker
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'device_tracker'                                            AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM device_tracker
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'device_tracker'                                                        AS relation,
    'vertical_accuracy'                                                     AS measure,
    'float'                                                                 AS kind,
    '-'                                                                     AS unit,
    '<on-change>'                                                           AS period,
    count(vertical_accuracy)                                                AS rows,
    CAST(min(time) FILTER (WHERE vertical_accuracy IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE vertical_accuracy IS NOT NULL) AS VARCHAR) AS newest
FROM device_tracker
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
    table_name = 'device_tracker'
    AND column_name NOT IN (
        'altitude', 'battery_level', 'entity_id', 'gps_accuracy', 'in_zones_str',
        'latitude', 'longitude', 'module', 'source_type_str', 'state', 'time',
        'tracking_type_str', 'value', 'vertical_accuracy'
    )
UNION ALL
SELECT
    'fan'                                                               AS relation,
    'assumed_state'                                                     AS measure,
    'float'                                                             AS kind,
    '-'                                                                 AS unit,
    '<on-change>'                                                       AS period,
    count(assumed_state)                                                AS rows,
    CAST(min(time) FILTER (WHERE assumed_state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE assumed_state IS NOT NULL) AS VARCHAR) AS newest
FROM fan
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'fan'                                                            AS relation,
    'percentage'                                                     AS measure,
    'float'                                                          AS kind,
    '-'                                                              AS unit,
    '<on-change>'                                                    AS period,
    count(percentage)                                                AS rows,
    CAST(min(time) FILTER (WHERE percentage IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE percentage IS NOT NULL) AS VARCHAR) AS newest
FROM fan
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'fan'                                                       AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM fan
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
    table_name = 'fan'
    AND column_name NOT IN (
        'assumed_state', 'direction_str', 'entity_id', 'module', 'percentage', 'state',
        'time', 'value'
    )
UNION ALL
SELECT
    'input_boolean'                                             AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM input_boolean
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
    table_name = 'input_boolean'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'light'                                                             AS relation,
    'assumed_state'                                                     AS measure,
    'float'                                                             AS kind,
    '-'                                                                 AS unit,
    '<on-change>'                                                       AS period,
    count(assumed_state)                                                AS rows,
    CAST(min(time) FILTER (WHERE assumed_state IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE assumed_state IS NOT NULL) AS VARCHAR) AS newest
FROM light
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'light'                                                          AS relation,
    'brightness'                                                     AS measure,
    'float'                                                          AS kind,
    '-'                                                              AS unit,
    '<on-change>'                                                    AS period,
    count(brightness)                                                AS rows,
    CAST(min(time) FILTER (WHERE brightness IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE brightness IS NOT NULL) AS VARCHAR) AS newest
FROM light
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'light'                                                                     AS relation,
    'max_color_temp_kelvin'                                                     AS measure,
    'float'                                                                     AS kind,
    '-'                                                                         AS unit,
    '<on-change>'                                                               AS period,
    count(max_color_temp_kelvin)                                                AS rows,
    CAST(min(time) FILTER (WHERE max_color_temp_kelvin IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE max_color_temp_kelvin IS NOT NULL) AS VARCHAR) AS newest
FROM light
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'light'                                                                     AS relation,
    'min_color_temp_kelvin'                                                     AS measure,
    'float'                                                                     AS kind,
    '-'                                                                         AS unit,
    '<on-change>'                                                               AS period,
    count(min_color_temp_kelvin)                                                AS rows,
    CAST(min(time) FILTER (WHERE min_color_temp_kelvin IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE min_color_temp_kelvin IS NOT NULL) AS VARCHAR) AS newest
FROM light
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'light'                                                         AS relation,
    'rgb_color'                                                     AS measure,
    'float'                                                         AS kind,
    '-'                                                             AS unit,
    '<on-change>'                                                   AS period,
    count(rgb_color)                                                AS rows,
    CAST(min(time) FILTER (WHERE rgb_color IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE rgb_color IS NOT NULL) AS VARCHAR) AS newest
FROM light
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'light'                                                     AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM light
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
    table_name = 'light'
    AND column_name NOT IN (
        'assumed_state', 'brightness', 'brightness_str', 'effect_list_str', 'effect_str',
        'entity_id', 'group_entities_str', 'max_color_temp_kelvin', 'min_color_temp_kelvin',
        'module', 'rgb_color', 'rgb_color_str', 'state', 'time', 'value'
    )
UNION ALL
SELECT
    'lock'                                                      AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM lock
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
    table_name = 'lock'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'media_player'                                              AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM media_player
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
    table_name = 'media_player'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'media_player__speaker'                                               AS relation,
    'is_volume_muted'                                                     AS measure,
    'float'                                                               AS kind,
    '-'                                                                   AS unit,
    '<on-change>'                                                         AS period,
    count(is_volume_muted)                                                AS rows,
    CAST(min(time) FILTER (WHERE is_volume_muted IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE is_volume_muted IS NOT NULL) AS VARCHAR) AS newest
FROM media_player__speaker
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'media_player__speaker'                                                AS relation,
    'media_album_name'                                                     AS measure,
    'float'                                                                AS kind,
    '-'                                                                    AS unit,
    '<on-change>'                                                          AS period,
    count(media_album_name)                                                AS rows,
    CAST(min(time) FILTER (WHERE media_album_name IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE media_album_name IS NOT NULL) AS VARCHAR) AS newest
FROM media_player__speaker
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'media_player__speaker'                                             AS relation,
    'media_channel'                                                     AS measure,
    'float'                                                             AS kind,
    '-'                                                                 AS unit,
    '<on-change>'                                                       AS period,
    count(media_channel)                                                AS rows,
    CAST(min(time) FILTER (WHERE media_channel IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE media_channel IS NOT NULL) AS VARCHAR) AS newest
FROM media_player__speaker
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'media_player__speaker'                                              AS relation,
    'media_duration'                                                     AS measure,
    'float'                                                              AS kind,
    '-'                                                                  AS unit,
    '<on-change>'                                                        AS period,
    count(media_duration)                                                AS rows,
    CAST(min(time) FILTER (WHERE media_duration IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE media_duration IS NOT NULL) AS VARCHAR) AS newest
FROM media_player__speaker
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'media_player__speaker'                                           AS relation,
    'media_title'                                                     AS measure,
    'float'                                                           AS kind,
    '-'                                                               AS unit,
    '<on-change>'                                                     AS period,
    count(media_title)                                                AS rows,
    CAST(min(time) FILTER (WHERE media_title IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE media_title IS NOT NULL) AS VARCHAR) AS newest
FROM media_player__speaker
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'media_player__speaker'                                     AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM media_player__speaker
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'media_player__speaker'                                            AS relation,
    'volume_level'                                                     AS measure,
    'float'                                                            AS kind,
    '-'                                                                AS unit,
    '<on-change>'                                                      AS period,
    count(volume_level)                                                AS rows,
    CAST(min(time) FILTER (WHERE volume_level IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE volume_level IS NOT NULL) AS VARCHAR) AS newest
FROM media_player__speaker
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
    table_name = 'media_player__speaker'
    AND column_name NOT IN (
        'app_name_str', 'entity_id', 'is_volume_muted', 'media_album_name',
        'media_album_name_str', 'media_artist_str', 'media_channel', 'media_channel_str',
        'media_content_type_str', 'media_duration', 'media_title', 'media_title_str',
        'module', 'state', 'time', 'value', 'volume_level'
    )
UNION ALL
SELECT
    'media_player__tv'                                          AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM media_player__tv
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
    table_name = 'media_player__tv'
    AND column_name NOT IN ('entity_id', 'module', 'state', 'time', 'value')
UNION ALL
SELECT
    'number'                                                  AS relation,
    'max'                                                     AS measure,
    'float'                                                   AS kind,
    '-'                                                       AS unit,
    '<on-change>'                                             AS period,
    count(max)                                                AS rows,
    CAST(min(time) FILTER (WHERE max IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE max IS NOT NULL) AS VARCHAR) AS newest
FROM number
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'number'                                                  AS relation,
    'min'                                                     AS measure,
    'float'                                                   AS kind,
    '-'                                                       AS unit,
    '<on-change>'                                             AS period,
    count(min)                                                AS rows,
    CAST(min(time) FILTER (WHERE min IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE min IS NOT NULL) AS VARCHAR) AS newest
FROM number
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'number'                                                   AS relation,
    'step'                                                     AS measure,
    'float'                                                    AS kind,
    '-'                                                        AS unit,
    '<on-change>'                                              AS period,
    count(step)                                                AS rows,
    CAST(min(time) FILTER (WHERE step IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE step IS NOT NULL) AS VARCHAR) AS newest
FROM number
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'number'                                                    AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM number
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
    table_name = 'number'
    AND column_name NOT IN ('entity_id', 'max', 'min', 'module', 'step', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'person'                                                           AS relation,
    'gps_accuracy'                                                     AS measure,
    'float'                                                            AS kind,
    '-'                                                                AS unit,
    '<on-change>'                                                      AS period,
    count(gps_accuracy)                                                AS rows,
    CAST(min(time) FILTER (WHERE gps_accuracy IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE gps_accuracy IS NOT NULL) AS VARCHAR) AS newest
FROM person
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'person'                                                       AS relation,
    'latitude'                                                     AS measure,
    'float'                                                        AS kind,
    '-'                                                            AS unit,
    '<on-change>'                                                  AS period,
    count(latitude)                                                AS rows,
    CAST(min(time) FILTER (WHERE latitude IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE latitude IS NOT NULL) AS VARCHAR) AS newest
FROM person
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'person'                                                        AS relation,
    'longitude'                                                     AS measure,
    'float'                                                         AS kind,
    '-'                                                             AS unit,
    '<on-change>'                                                   AS period,
    count(longitude)                                                AS rows,
    CAST(min(time) FILTER (WHERE longitude IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE longitude IS NOT NULL) AS VARCHAR) AS newest
FROM person
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'person'                                                    AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM person
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
    table_name = 'person'
    AND column_name NOT IN (
        'device_trackers_str', 'entity_id', 'gps_accuracy', 'in_zones_str', 'latitude',
        'longitude', 'module', 'state', 'time', 'value'
    )
UNION ALL
SELECT
    'sensor'                                                                                                                              AS relation,
    'Active Alarm (BAYSWATER, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 810058)'                                                       AS measure,
    'float'                                                                                                                               AS kind,
    '-'                                                                                                                                   AS unit,
    '<on-change>'                                                                                                                         AS period,
    count("Active Alarm (BAYSWATER, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 810058)")                                                AS rows,
    CAST(min(time) FILTER (WHERE "Active Alarm (BAYSWATER, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 810058)" IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE "Active Alarm (BAYSWATER, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 810058)" IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                                                                                             AS relation,
    'Active Alarm (EMBLETON, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 810033)'                                                       AS measure,
    'float'                                                                                                                              AS kind,
    '-'                                                                                                                                  AS unit,
    '<on-change>'                                                                                                                        AS period,
    count("Active Alarm (EMBLETON, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 810033)")                                                AS rows,
    CAST(min(time) FILTER (WHERE "Active Alarm (EMBLETON, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 810033)" IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE "Active Alarm (EMBLETON, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 810033)" IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                                                                                         AS relation,
    'Active Alarm (GUILDFORD, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809971)'                                                       AS measure,
    'float'                                                                                                                          AS kind,
    '-'                                                                                                                              AS unit,
    '<on-change>'                                                                                                                    AS period,
    count("Active Alarm (GUILDFORD, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809971)")                                                AS rows,
    CAST(min(time) FILTER (WHERE "Active Alarm (GUILDFORD, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809971)" IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE "Active Alarm (GUILDFORD, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809971)" IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                          AS relation,
    'Available'                                                       AS measure,
    'float'                                                           AS kind,
    '-'                                                               AS unit,
    '<on-change>'                                                     AS period,
    count("Available")                                                AS rows,
    CAST(min(time) FILTER (WHERE "Available" IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE "Available" IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                                      AS relation,
    'Available (Important)'                                                       AS measure,
    'float'                                                                       AS kind,
    '-'                                                                           AS unit,
    '<on-change>'                                                                 AS period,
    count("Available (Important)")                                                AS rows,
    CAST(min(time) FILTER (WHERE "Available (Important)" IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE "Available (Important)" IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                                          AS relation,
    'Available (Opportunistic)'                                                       AS measure,
    'float'                                                                           AS kind,
    '-'                                                                               AS unit,
    '<on-change>'                                                                     AS period,
    count("Available (Opportunistic)")                                                AS rows,
    CAST(min(time) FILTER (WHERE "Available (Opportunistic)" IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE "Available (Opportunistic)" IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                                                                                 AS relation,
    'Burn Off (LEXIA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809996)'                                                       AS measure,
    'float'                                                                                                                  AS kind,
    '-'                                                                                                                      AS unit,
    '<on-change>'                                                                                                            AS period,
    count("Burn Off (LEXIA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809996)")                                                AS rows,
    CAST(min(time) FILTER (WHERE "Burn Off (LEXIA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809996)" IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE "Burn Off (LEXIA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809996)" IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                                                                                    AS relation,
    'Burn Off (WHITEMAN, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810037)'                                                       AS measure,
    'float'                                                                                                                     AS kind,
    '-'                                                                                                                         AS unit,
    '<on-change>'                                                                                                               AS period,
    count("Burn Off (WHITEMAN, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810037)")                                                AS rows,
    CAST(min(time) FILTER (WHERE "Burn Off (WHITEMAN, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810037)" IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE "Burn Off (WHITEMAN, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810037)" IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                                                                                          AS relation,
    'Burn Off (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810023)'                                                       AS measure,
    'float'                                                                                                                           AS kind,
    '-'                                                                                                                               AS unit,
    '<on-change>'                                                                                                                     AS period,
    count("Burn Off (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810023)")                                                AS rows,
    CAST(min(time) FILTER (WHERE "Burn Off (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810023)" IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE "Burn Off (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810023)" IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                                                                                          AS relation,
    'Bushfire (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810022)'                                                       AS measure,
    'float'                                                                                                                           AS kind,
    '-'                                                                                                                               AS unit,
    '<on-change>'                                                                                                                     AS period,
    count("Bushfire (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810022)")                                                AS rows,
    CAST(min(time) FILTER (WHERE "Bushfire (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810022)" IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE "Bushfire (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810022)" IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                                                                                    AS relation,
    'Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)'                                                       AS measure,
    'float'                                                                                                                     AS kind,
    '-'                                                                                                                         AS unit,
    '<on-change>'                                                                                                               AS period,
    count("Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)")                                                AS rows,
    CAST(min(time) FILTER (WHERE "Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)" IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE "Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)" IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                               AS relation,
    'Low Power Mode'                                                       AS measure,
    'float'                                                                AS kind,
    '-'                                                                    AS unit,
    '<on-change>'                                                          AS period,
    count("Low Power Mode")                                                AS rows,
    CAST(min(time) FILTER (WHERE "Low Power Mode" IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE "Low Power Mode" IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                     AS relation,
    'Name'                                                       AS measure,
    'float'                                                      AS kind,
    '-'                                                          AS unit,
    '<on-change>'                                                AS period,
    count("Name")                                                AS rows,
    CAST(min(time) FILTER (WHERE "Name" IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE "Name" IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                            AS relation,
    'Postal Code'                                                       AS measure,
    'float'                                                             AS kind,
    '-'                                                                 AS unit,
    '<on-change>'                                                       AS period,
    count("Postal Code")                                                AS rows,
    CAST(min(time) FILTER (WHERE "Postal Code" IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE "Postal Code" IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                                                                                       AS relation,
    'Road Crash (BALLAJURA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810011)'                                                       AS measure,
    'float'                                                                                                                        AS kind,
    '-'                                                                                                                            AS unit,
    '<on-change>'                                                                                                                  AS period,
    count("Road Crash (BALLAJURA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810011)")                                                AS rows,
    CAST(min(time) FILTER (WHERE "Road Crash (BALLAJURA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810011)" IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE "Road Crash (BALLAJURA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810011)" IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                                                                                         AS relation,
    'Road Crash (MORLEY, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 809968)'                                                       AS measure,
    'float'                                                                                                                          AS kind,
    '-'                                                                                                                              AS unit,
    '<on-change>'                                                                                                                    AS period,
    count("Road Crash (MORLEY, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 809968)")                                                AS rows,
    CAST(min(time) FILTER (WHERE "Road Crash (MORLEY, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 809968)" IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE "Road Crash (MORLEY, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 809968)" IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                                                                                              AS relation,
    'Structure Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)'                                                       AS measure,
    'float'                                                                                                                               AS kind,
    '-'                                                                                                                                   AS unit,
    '<on-change>'                                                                                                                         AS period,
    count("Structure Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)")                                                AS rows,
    CAST(min(time) FILTER (WHERE "Structure Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)" IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE "Structure Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)" IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                                 AS relation,
    'Sub Thoroughfare'                                                       AS measure,
    'float'                                                                  AS kind,
    '-'                                                                      AS unit,
    '<on-change>'                                                            AS period,
    count("Sub Thoroughfare")                                                AS rows,
    CAST(min(time) FILTER (WHERE "Sub Thoroughfare" IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE "Sub Thoroughfare" IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                      AS relation,
    'Total'                                                       AS measure,
    'float'                                                       AS kind,
    '-'                                                           AS unit,
    '<on-change>'                                                 AS period,
    count("Total")                                                AS rows,
    CAST(min(time) FILTER (WHERE "Total" IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE "Total" IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                     AS relation,
    'bom_id'                                                     AS measure,
    'float'                                                      AS kind,
    '-'                                                          AS unit,
    '<on-change>'                                                AS period,
    count(bom_id)                                                AS rows,
    CAST(min(time) FILTER (WHERE bom_id IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE bom_id IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                   AS relation,
    'date'                                                     AS measure,
    'float'                                                    AS kind,
    '-'                                                        AS unit,
    '<on-change>'                                              AS period,
    count(date)                                                AS rows,
    CAST(min(time) FILTER (WHERE date IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE date IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                       AS relation,
    'distance'                                                     AS measure,
    'float'                                                        AS kind,
    '-'                                                            AS unit,
    '<on-change>'                                                  AS period,
    count(distance)                                                AS rows,
    CAST(min(time) FILTER (WHERE distance IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE distance IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                         AS relation,
    'issue_time'                                                     AS measure,
    'float'                                                          AS kind,
    '-'                                                              AS unit,
    '<on-change>'                                                    AS period,
    count(issue_time)                                                AS rows,
    CAST(min(time) FILTER (WHERE issue_time IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE issue_time IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                              AS relation,
    'next_issue_time'                                                     AS measure,
    'float'                                                               AS kind,
    '-'                                                                   AS unit,
    '<on-change>'                                                         AS period,
    count(next_issue_time)                                                AS rows,
    CAST(min(time) FILTER (WHERE next_issue_time IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE next_issue_time IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                         AS relation,
    'next_reset'                                                     AS measure,
    'float'                                                          AS kind,
    '-'                                                              AS unit,
    '<on-change>'                                                    AS period,
    count(next_reset)                                                AS rows,
    CAST(min(time) FILTER (WHERE next_reset IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE next_reset IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                               AS relation,
    'observation_time'                                                     AS measure,
    'float'                                                                AS kind,
    '-'                                                                    AS unit,
    '<on-change>'                                                          AS period,
    count(observation_time)                                                AS rows,
    CAST(min(time) FILTER (WHERE observation_time IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE observation_time IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor'                                                                 AS relation,
    'response_timestamp'                                                     AS measure,
    'float'                                                                  AS kind,
    '-'                                                                      AS unit,
    '<on-change>'                                                            AS period,
    count(response_timestamp)                                                AS rows,
    CAST(min(time) FILTER (WHERE response_timestamp IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE response_timestamp IS NOT NULL) AS VARCHAR) AS newest
FROM sensor
WHERE
    module = 'homeassistant'
UNION ALL
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
    AND column_name NOT IN (
        'Active Alarm (BAYSWATER, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 810058)',
        'Active Alarm (BAYSWATER, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 810058)_str',
        'Active Alarm (EMBLETON, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 810033)',
        'Active Alarm (EMBLETON, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 810033)_str',
        'Active Alarm (GUILDFORD, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809971)',
        'Active Alarm (GUILDFORD, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809971)_str',
        'Administrative Area_str', 'Areas Of Interest_str', 'Available',
        'Available (Important)', 'Available (Important)_str', 'Available (Opportunistic)',
        'Available (Opportunistic)_str', 'Available_str',
        'Burn Off (LEXIA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809996)',
        'Burn Off (LEXIA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809996)_str',
        'Burn Off (WHITEMAN, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810037)',
        'Burn Off (WHITEMAN, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810037)_str',
        'Burn Off (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810023)',
        'Burn Off (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810023)_str',
        'Bushfire (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810022)',
        'Bushfire (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810022)_str',
        'Cellular Technology_str', 'Confidence_str', 'Country_str',
        'Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)',
        'Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)_str',
        'Fire (SWAN VIEW, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810055)_str',
        'ISO Country Code_str',
        'Incident (MIDLAND, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809976)_str',
        'Incident (MIDLAND, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810043)_str',
        'Inland Water_str', 'Locality_str', 'Location_str', 'Low Power Mode', 'Name',
        'Name_str', 'Ocean_str', 'Postal Code',
        'Road Crash (BALLAJURA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810011)',
        'Road Crash (BALLAJURA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810011)_str',
        'Road Crash (MORLEY, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 809968)',
        'Road Crash (MORLEY, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 809968)_str',
        'Structure Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)',
        'Structure Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)_str',
        'Sub Administrative Area_str', 'Sub Locality_str', 'Sub Thoroughfare',
        'Thoroughfare_str', 'Time Zone_str', 'Total', 'Total_str', 'Types_str', 'Zones_str',
        'bom_id', 'copyright_str', 'date', 'date_str', 'distance', 'entity_id',
        'forecast_region_str', 'forecast_text_str', 'forecast_type_str', 'issue_time',
        'issue_time_str', 'last_valid_state_str', 'module', 'name_str', 'next_issue_time',
        'next_issue_time_str', 'next_reset', 'next_reset_str', 'observation_time',
        'observation_time_str', 'response_timestamp', 'response_timestamp_str', 'state',
        'state__str', 'time', 'unit_of_measurement', 'value', 'warnings_str'
    )
UNION ALL
SELECT
    'sensor__atmospheric_pressure'                                 AS relation,
    'latitude'                                                     AS measure,
    'float'                                                        AS kind,
    '-'                                                            AS unit,
    '<on-change>'                                                  AS period,
    count(latitude)                                                AS rows,
    CAST(min(time) FILTER (WHERE latitude IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE latitude IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__atmospheric_pressure
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__atmospheric_pressure'                                  AS relation,
    'longitude'                                                     AS measure,
    'float'                                                         AS kind,
    '-'                                                             AS unit,
    '<on-change>'                                                   AS period,
    count(longitude)                                                AS rows,
    CAST(min(time) FILTER (WHERE longitude IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE longitude IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__atmospheric_pressure
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__atmospheric_pressure'                              AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__atmospheric_pressure
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
    table_name = 'sensor__atmospheric_pressure'
    AND column_name NOT IN (
        'entity_id', 'latitude', 'longitude', 'module', 'time', 'unit_of_measurement',
        'value'
    )
UNION ALL
SELECT
    'sensor__battery'                                              AS relation,
    'latitude'                                                     AS measure,
    'float'                                                        AS kind,
    '-'                                                            AS unit,
    '<on-change>'                                                  AS period,
    count(latitude)                                                AS rows,
    CAST(min(time) FILTER (WHERE latitude IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE latitude IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__battery
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__battery'                                               AS relation,
    'longitude'                                                     AS measure,
    'float'                                                         AS kind,
    '-'                                                             AS unit,
    '<on-change>'                                                   AS period,
    count(longitude)                                                AS rows,
    CAST(min(time) FILTER (WHERE longitude IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE longitude IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__battery
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__battery'                                           AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__battery
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
    table_name = 'sensor__battery'
    AND column_name NOT IN (
        'entity_id', 'latitude', 'longitude', 'module', 'time', 'unit_of_measurement',
        'value'
    )
UNION ALL
SELECT
    'sensor__carbon_dioxide'                                       AS relation,
    'latitude'                                                     AS measure,
    'float'                                                        AS kind,
    '-'                                                            AS unit,
    '<on-change>'                                                  AS period,
    count(latitude)                                                AS rows,
    CAST(min(time) FILTER (WHERE latitude IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE latitude IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__carbon_dioxide
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__carbon_dioxide'                                        AS relation,
    'longitude'                                                     AS measure,
    'float'                                                         AS kind,
    '-'                                                             AS unit,
    '<on-change>'                                                   AS period,
    count(longitude)                                                AS rows,
    CAST(min(time) FILTER (WHERE longitude IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE longitude IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__carbon_dioxide
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__carbon_dioxide'                                    AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__carbon_dioxide
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
    table_name = 'sensor__carbon_dioxide'
    AND column_name NOT IN (
        'entity_id', 'latitude', 'longitude', 'module', 'time', 'unit_of_measurement',
        'value'
    )
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
    'sensor__enum'                                                 AS relation,
    'latitude'                                                     AS measure,
    'float'                                                        AS kind,
    '-'                                                            AS unit,
    '<on-change>'                                                  AS period,
    count(latitude)                                                AS rows,
    CAST(min(time) FILTER (WHERE latitude IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE latitude IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__enum
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__enum'                                                  AS relation,
    'longitude'                                                     AS measure,
    'float'                                                         AS kind,
    '-'                                                             AS unit,
    '<on-change>'                                                   AS period,
    count(longitude)                                                AS rows,
    CAST(min(time) FILTER (WHERE longitude IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE longitude IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__enum
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
    table_name = 'sensor__enum'
    AND column_name NOT IN ('entity_id', 'latitude', 'longitude', 'module', 'options_str', 'state', 'time')
UNION ALL
SELECT
    'sensor__humidity'                                           AS relation,
    'bom_id'                                                     AS measure,
    'float'                                                      AS kind,
    '-'                                                          AS unit,
    '<on-change>'                                                AS period,
    count(bom_id)                                                AS rows,
    CAST(min(time) FILTER (WHERE bom_id IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE bom_id IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__humidity
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__humidity'                                             AS relation,
    'distance'                                                     AS measure,
    'float'                                                        AS kind,
    '-'                                                            AS unit,
    '<on-change>'                                                  AS period,
    count(distance)                                                AS rows,
    CAST(min(time) FILTER (WHERE distance IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE distance IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__humidity
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__humidity'                                               AS relation,
    'issue_time'                                                     AS measure,
    'float'                                                          AS kind,
    '-'                                                              AS unit,
    '<on-change>'                                                    AS period,
    count(issue_time)                                                AS rows,
    CAST(min(time) FILTER (WHERE issue_time IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE issue_time IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__humidity
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__humidity'                                             AS relation,
    'latitude'                                                     AS measure,
    'float'                                                        AS kind,
    '-'                                                            AS unit,
    '<on-change>'                                                  AS period,
    count(latitude)                                                AS rows,
    CAST(min(time) FILTER (WHERE latitude IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE latitude IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__humidity
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__humidity'                                              AS relation,
    'longitude'                                                     AS measure,
    'float'                                                         AS kind,
    '-'                                                             AS unit,
    '<on-change>'                                                   AS period,
    count(longitude)                                                AS rows,
    CAST(min(time) FILTER (WHERE longitude IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE longitude IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__humidity
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__humidity'                                                     AS relation,
    'observation_time'                                                     AS measure,
    'float'                                                                AS kind,
    '-'                                                                    AS unit,
    '<on-change>'                                                          AS period,
    count(observation_time)                                                AS rows,
    CAST(min(time) FILTER (WHERE observation_time IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE observation_time IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__humidity
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__humidity'                                                       AS relation,
    'response_timestamp'                                                     AS measure,
    'float'                                                                  AS kind,
    '-'                                                                      AS unit,
    '<on-change>'                                                            AS period,
    count(response_timestamp)                                                AS rows,
    CAST(min(time) FILTER (WHERE response_timestamp IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE response_timestamp IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__humidity
WHERE
    module = 'homeassistant'
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
    AND column_name NOT IN (
        'bom_id', 'copyright_str', 'distance', 'entity_id', 'issue_time', 'issue_time_str',
        'latitude', 'longitude', 'module', 'name_str', 'observation_time',
        'observation_time_str', 'response_timestamp', 'response_timestamp_str', 'time',
        'unit_of_measurement', 'value'
    )
UNION ALL
SELECT
    'sensor__pm25'                                              AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__pm25
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
    table_name = 'sensor__pm25'
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
    AND column_name NOT IN (
        'energy_sensor_entity_id_str', 'entity_id', 'module', 'time', 'unit_of_measurement',
        'value'
    )
UNION ALL
SELECT
    'sensor__precipitation'                                    AS relation,
    'date'                                                     AS measure,
    'float'                                                    AS kind,
    '-'                                                        AS unit,
    '<on-change>'                                              AS period,
    count(date)                                                AS rows,
    CAST(min(time) FILTER (WHERE date IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE date IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__precipitation
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__precipitation'                                          AS relation,
    'issue_time'                                                     AS measure,
    'float'                                                          AS kind,
    '-'                                                              AS unit,
    '<on-change>'                                                    AS period,
    count(issue_time)                                                AS rows,
    CAST(min(time) FILTER (WHERE issue_time IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE issue_time IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__precipitation
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__precipitation'                                               AS relation,
    'next_issue_time'                                                     AS measure,
    'float'                                                               AS kind,
    '-'                                                                   AS unit,
    '<on-change>'                                                         AS period,
    count(next_issue_time)                                                AS rows,
    CAST(min(time) FILTER (WHERE next_issue_time IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE next_issue_time IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__precipitation
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__precipitation'                                                  AS relation,
    'response_timestamp'                                                     AS measure,
    'float'                                                                  AS kind,
    '-'                                                                      AS unit,
    '<on-change>'                                                            AS period,
    count(response_timestamp)                                                AS rows,
    CAST(min(time) FILTER (WHERE response_timestamp IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE response_timestamp IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__precipitation
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__precipitation'                                     AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__precipitation
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
    table_name = 'sensor__precipitation'
    AND column_name NOT IN (
        'copyright_str', 'date', 'date_str', 'entity_id', 'forecast_region_str',
        'forecast_type_str', 'issue_time', 'issue_time_str', 'module', 'next_issue_time',
        'next_issue_time_str', 'response_timestamp', 'response_timestamp_str', 'time',
        'unit_of_measurement', 'value'
    )
UNION ALL
SELECT
    'sensor__pressure'                                          AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__pressure
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
    table_name = 'sensor__pressure'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'sensor__signal_strength'                                   AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__signal_strength
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
    table_name = 'sensor__signal_strength'
    AND column_name NOT IN ('entity_id', 'module', 'time', 'unit_of_measurement', 'value')
UNION ALL
SELECT
    'sensor__sound_pressure'                                       AS relation,
    'latitude'                                                     AS measure,
    'float'                                                        AS kind,
    '-'                                                            AS unit,
    '<on-change>'                                                  AS period,
    count(latitude)                                                AS rows,
    CAST(min(time) FILTER (WHERE latitude IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE latitude IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__sound_pressure
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__sound_pressure'                                        AS relation,
    'longitude'                                                     AS measure,
    'float'                                                         AS kind,
    '-'                                                             AS unit,
    '<on-change>'                                                   AS period,
    count(longitude)                                                AS rows,
    CAST(min(time) FILTER (WHERE longitude IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE longitude IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__sound_pressure
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__sound_pressure'                                    AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__sound_pressure
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
    table_name = 'sensor__sound_pressure'
    AND column_name NOT IN (
        'entity_id', 'latitude', 'longitude', 'module', 'time', 'unit_of_measurement',
        'value'
    )
UNION ALL
SELECT
    'sensor__temperature'                                        AS relation,
    'bom_id'                                                     AS measure,
    'float'                                                      AS kind,
    '-'                                                          AS unit,
    '<on-change>'                                                AS period,
    count(bom_id)                                                AS rows,
    CAST(min(time) FILTER (WHERE bom_id IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE bom_id IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__temperature
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__temperature'                                      AS relation,
    'date'                                                     AS measure,
    'float'                                                    AS kind,
    '-'                                                        AS unit,
    '<on-change>'                                              AS period,
    count(date)                                                AS rows,
    CAST(min(time) FILTER (WHERE date IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE date IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__temperature
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__temperature'                                          AS relation,
    'distance'                                                     AS measure,
    'float'                                                        AS kind,
    '-'                                                            AS unit,
    '<on-change>'                                                  AS period,
    count(distance)                                                AS rows,
    CAST(min(time) FILTER (WHERE distance IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE distance IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__temperature
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__temperature'                                            AS relation,
    'issue_time'                                                     AS measure,
    'float'                                                          AS kind,
    '-'                                                              AS unit,
    '<on-change>'                                                    AS period,
    count(issue_time)                                                AS rows,
    CAST(min(time) FILTER (WHERE issue_time IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE issue_time IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__temperature
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__temperature'                                          AS relation,
    'latitude'                                                     AS measure,
    'float'                                                        AS kind,
    '-'                                                            AS unit,
    '<on-change>'                                                  AS period,
    count(latitude)                                                AS rows,
    CAST(min(time) FILTER (WHERE latitude IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE latitude IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__temperature
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__temperature'                                           AS relation,
    'longitude'                                                     AS measure,
    'float'                                                         AS kind,
    '-'                                                             AS unit,
    '<on-change>'                                                   AS period,
    count(longitude)                                                AS rows,
    CAST(min(time) FILTER (WHERE longitude IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE longitude IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__temperature
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__temperature'                                                 AS relation,
    'next_issue_time'                                                     AS measure,
    'float'                                                               AS kind,
    '-'                                                                   AS unit,
    '<on-change>'                                                         AS period,
    count(next_issue_time)                                                AS rows,
    CAST(min(time) FILTER (WHERE next_issue_time IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE next_issue_time IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__temperature
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__temperature'                                                  AS relation,
    'observation_time'                                                     AS measure,
    'float'                                                                AS kind,
    '-'                                                                    AS unit,
    '<on-change>'                                                          AS period,
    count(observation_time)                                                AS rows,
    CAST(min(time) FILTER (WHERE observation_time IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE observation_time IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__temperature
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__temperature'                                                    AS relation,
    'response_timestamp'                                                     AS measure,
    'float'                                                                  AS kind,
    '-'                                                                      AS unit,
    '<on-change>'                                                            AS period,
    count(response_timestamp)                                                AS rows,
    CAST(min(time) FILTER (WHERE response_timestamp IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE response_timestamp IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__temperature
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__temperature'                                               AS relation,
    'time_observed'                                                     AS measure,
    'float'                                                             AS kind,
    '-'                                                                 AS unit,
    '<on-change>'                                                       AS period,
    count(time_observed)                                                AS rows,
    CAST(min(time) FILTER (WHERE time_observed IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE time_observed IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__temperature
WHERE
    module = 'homeassistant'
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
    AND column_name NOT IN (
        'bom_id', 'copyright_str', 'date', 'date_str', 'distance', 'entity_id',
        'forecast_region_str', 'forecast_type_str', 'issue_time', 'issue_time_str',
        'latitude', 'longitude', 'module', 'name_str', 'next_issue_time',
        'next_issue_time_str', 'observation_time', 'observation_time_str',
        'response_timestamp', 'response_timestamp_str', 'time', 'time_observed',
        'time_observed_str', 'unit_of_measurement', 'value'
    )
UNION ALL
SELECT
    'sensor__timestamp'                                        AS relation,
    'date'                                                     AS measure,
    'float'                                                    AS kind,
    '-'                                                        AS unit,
    '<on-change>'                                              AS period,
    count(date)                                                AS rows,
    CAST(min(time) FILTER (WHERE date IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE date IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__timestamp
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__timestamp'                                              AS relation,
    'issue_time'                                                     AS measure,
    'float'                                                          AS kind,
    '-'                                                              AS unit,
    '<on-change>'                                                    AS period,
    count(issue_time)                                                AS rows,
    CAST(min(time) FILTER (WHERE issue_time IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE issue_time IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__timestamp
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__timestamp'                                                   AS relation,
    'next_issue_time'                                                     AS measure,
    'float'                                                               AS kind,
    '-'                                                                   AS unit,
    '<on-change>'                                                         AS period,
    count(next_issue_time)                                                AS rows,
    CAST(min(time) FILTER (WHERE next_issue_time IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE next_issue_time IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__timestamp
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__timestamp'                                                      AS relation,
    'response_timestamp'                                                     AS measure,
    'float'                                                                  AS kind,
    '-'                                                                      AS unit,
    '<on-change>'                                                            AS period,
    count(response_timestamp)                                                AS rows,
    CAST(min(time) FILTER (WHERE response_timestamp IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE response_timestamp IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__timestamp
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
    table_name = 'sensor__timestamp'
    AND column_name NOT IN (
        'copyright_str', 'date', 'date_str', 'entity_id', 'forecast_region_str',
        'forecast_type_str', 'issue_time', 'issue_time_str', 'module', 'next_issue_time',
        'next_issue_time_str', 'response_timestamp', 'response_timestamp_str', 'state',
        'time'
    )
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
    'sensor__wind_speed'                                         AS relation,
    'bom_id'                                                     AS measure,
    'float'                                                      AS kind,
    '-'                                                          AS unit,
    '<on-change>'                                                AS period,
    count(bom_id)                                                AS rows,
    CAST(min(time) FILTER (WHERE bom_id IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE bom_id IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__wind_speed
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__wind_speed'                                           AS relation,
    'distance'                                                     AS measure,
    'float'                                                        AS kind,
    '-'                                                            AS unit,
    '<on-change>'                                                  AS period,
    count(distance)                                                AS rows,
    CAST(min(time) FILTER (WHERE distance IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE distance IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__wind_speed
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__wind_speed'                                             AS relation,
    'issue_time'                                                     AS measure,
    'float'                                                          AS kind,
    '-'                                                              AS unit,
    '<on-change>'                                                    AS period,
    count(issue_time)                                                AS rows,
    CAST(min(time) FILTER (WHERE issue_time IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE issue_time IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__wind_speed
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__wind_speed'                                                   AS relation,
    'observation_time'                                                     AS measure,
    'float'                                                                AS kind,
    '-'                                                                    AS unit,
    '<on-change>'                                                          AS period,
    count(observation_time)                                                AS rows,
    CAST(min(time) FILTER (WHERE observation_time IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE observation_time IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__wind_speed
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__wind_speed'                                                     AS relation,
    'response_timestamp'                                                     AS measure,
    'float'                                                                  AS kind,
    '-'                                                                      AS unit,
    '<on-change>'                                                            AS period,
    count(response_timestamp)                                                AS rows,
    CAST(min(time) FILTER (WHERE response_timestamp IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE response_timestamp IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__wind_speed
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sensor__wind_speed'                                        AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sensor__wind_speed
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
    table_name = 'sensor__wind_speed'
    AND column_name NOT IN (
        'bom_id', 'copyright_str', 'distance', 'entity_id', 'issue_time', 'issue_time_str',
        'module', 'name_str', 'observation_time', 'observation_time_str',
        'response_timestamp', 'response_timestamp_str', 'time', 'unit_of_measurement',
        'value'
    )
UNION ALL
SELECT
    'sun'                                                         AS relation,
    'azimuth'                                                     AS measure,
    'float'                                                       AS kind,
    '-'                                                           AS unit,
    '<on-change>'                                                 AS period,
    count(azimuth)                                                AS rows,
    CAST(min(time) FILTER (WHERE azimuth IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE azimuth IS NOT NULL) AS VARCHAR) AS newest
FROM sun
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sun'                                                           AS relation,
    'elevation'                                                     AS measure,
    'float'                                                         AS kind,
    '-'                                                             AS unit,
    '<on-change>'                                                   AS period,
    count(elevation)                                                AS rows,
    CAST(min(time) FILTER (WHERE elevation IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE elevation IS NOT NULL) AS VARCHAR) AS newest
FROM sun
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sun'                                                           AS relation,
    'next_dawn'                                                     AS measure,
    'float'                                                         AS kind,
    '-'                                                             AS unit,
    '<on-change>'                                                   AS period,
    count(next_dawn)                                                AS rows,
    CAST(min(time) FILTER (WHERE next_dawn IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE next_dawn IS NOT NULL) AS VARCHAR) AS newest
FROM sun
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sun'                                                           AS relation,
    'next_dusk'                                                     AS measure,
    'float'                                                         AS kind,
    '-'                                                             AS unit,
    '<on-change>'                                                   AS period,
    count(next_dusk)                                                AS rows,
    CAST(min(time) FILTER (WHERE next_dusk IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE next_dusk IS NOT NULL) AS VARCHAR) AS newest
FROM sun
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sun'                                                             AS relation,
    'next_rising'                                                     AS measure,
    'float'                                                           AS kind,
    '-'                                                               AS unit,
    '<on-change>'                                                     AS period,
    count(next_rising)                                                AS rows,
    CAST(min(time) FILTER (WHERE next_rising IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE next_rising IS NOT NULL) AS VARCHAR) AS newest
FROM sun
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sun'                                                              AS relation,
    'next_setting'                                                     AS measure,
    'float'                                                            AS kind,
    '-'                                                                AS unit,
    '<on-change>'                                                      AS period,
    count(next_setting)                                                AS rows,
    CAST(min(time) FILTER (WHERE next_setting IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE next_setting IS NOT NULL) AS VARCHAR) AS newest
FROM sun
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sun'                                                        AS relation,
    'rising'                                                     AS measure,
    'float'                                                      AS kind,
    '-'                                                          AS unit,
    '<on-change>'                                                AS period,
    count(rising)                                                AS rows,
    CAST(min(time) FILTER (WHERE rising IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE rising IS NOT NULL) AS VARCHAR) AS newest
FROM sun
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'sun'                                                       AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM sun
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
    table_name = 'sun'
    AND column_name NOT IN (
        'azimuth', 'elevation', 'entity_id', 'module', 'next_dawn', 'next_dawn_str',
        'next_dusk', 'next_dusk_str', 'next_rising', 'next_rising_str', 'next_setting',
        'next_setting_str', 'rising', 'state', 'time', 'value'
    )
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
        'brightness_pct_str', 'configuration_str', 'entity_id', 'force_rgb_color',
        'force_rgb_color_str', 'module', 'rgb_color', 'rgb_color_str', 'state',
        'sun_position', 'sun_position_str', 'time', 'value'
    )
UNION ALL
SELECT
    'update__firmware'                                                AS relation,
    'auto_update'                                                     AS measure,
    'float'                                                           AS kind,
    '-'                                                               AS unit,
    '<on-change>'                                                     AS period,
    count(auto_update)                                                AS rows,
    CAST(min(time) FILTER (WHERE auto_update IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE auto_update IS NOT NULL) AS VARCHAR) AS newest
FROM update__firmware
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'update__firmware'                                                      AS relation,
    'display_precision'                                                     AS measure,
    'float'                                                                 AS kind,
    '-'                                                                     AS unit,
    '<on-change>'                                                           AS period,
    count(display_precision)                                                AS rows,
    CAST(min(time) FILTER (WHERE display_precision IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE display_precision IS NOT NULL) AS VARCHAR) AS newest
FROM update__firmware
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'update__firmware'                                                AS relation,
    'in_progress'                                                     AS measure,
    'float'                                                           AS kind,
    '-'                                                               AS unit,
    '<on-change>'                                                     AS period,
    count(in_progress)                                                AS rows,
    CAST(min(time) FILTER (WHERE in_progress IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE in_progress IS NOT NULL) AS VARCHAR) AS newest
FROM update__firmware
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'update__firmware'                                                      AS relation,
    'installed_version'                                                     AS measure,
    'float'                                                                 AS kind,
    '-'                                                                     AS unit,
    '<on-change>'                                                           AS period,
    count(installed_version)                                                AS rows,
    CAST(min(time) FILTER (WHERE installed_version IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE installed_version IS NOT NULL) AS VARCHAR) AS newest
FROM update__firmware
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'update__firmware'                                                   AS relation,
    'latest_version'                                                     AS measure,
    'float'                                                              AS kind,
    '-'                                                                  AS unit,
    '<on-change>'                                                        AS period,
    count(latest_version)                                                AS rows,
    CAST(min(time) FILTER (WHERE latest_version IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE latest_version IS NOT NULL) AS VARCHAR) AS newest
FROM update__firmware
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'update__firmware'                                                      AS relation,
    'update_percentage'                                                     AS measure,
    'float'                                                                 AS kind,
    '-'                                                                     AS unit,
    '<on-change>'                                                           AS period,
    count(update_percentage)                                                AS rows,
    CAST(min(time) FILTER (WHERE update_percentage IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE update_percentage IS NOT NULL) AS VARCHAR) AS newest
FROM update__firmware
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'update__firmware'                                          AS relation,
    'value'                                                     AS measure,
    'float'                                                     AS kind,
    '-'                                                         AS unit,
    '<on-change>'                                               AS period,
    count(value)                                                AS rows,
    CAST(min(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE value IS NOT NULL) AS VARCHAR) AS newest
FROM update__firmware
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
    table_name = 'update__firmware'
    AND column_name NOT IN (
        'auto_update', 'display_precision', 'entity_id', 'in_progress', 'installed_version',
        'latest_version', 'module', 'release_summary_str', 'release_url_str',
        'skipped_version_str', 'state', 'time', 'title_str', 'update_percentage',
        'update_percentage_str', 'value'
    )
UNION ALL
SELECT
    'weather'                                                                  AS relation,
    'apparent_temperature'                                                     AS measure,
    'float'                                                                    AS kind,
    '-'                                                                        AS unit,
    '<on-change>'                                                              AS period,
    count(apparent_temperature)                                                AS rows,
    CAST(min(time) FILTER (WHERE apparent_temperature IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE apparent_temperature IS NOT NULL) AS VARCHAR) AS newest
FROM weather
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'weather'                                                       AS relation,
    'dew_point'                                                     AS measure,
    'float'                                                         AS kind,
    '-'                                                             AS unit,
    '<on-change>'                                                   AS period,
    count(dew_point)                                                AS rows,
    CAST(min(time) FILTER (WHERE dew_point IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE dew_point IS NOT NULL) AS VARCHAR) AS newest
FROM weather
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'weather'                                                      AS relation,
    'humidity'                                                     AS measure,
    'float'                                                        AS kind,
    '-'                                                            AS unit,
    '<on-change>'                                                  AS period,
    count(humidity)                                                AS rows,
    CAST(min(time) FILTER (WHERE humidity IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE humidity IS NOT NULL) AS VARCHAR) AS newest
FROM weather
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'weather'                                                        AS relation,
    'later_temp'                                                     AS measure,
    'float'                                                          AS kind,
    '-'                                                              AS unit,
    '<on-change>'                                                    AS period,
    count(later_temp)                                                AS rows,
    CAST(min(time) FILTER (WHERE later_temp IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE later_temp IS NOT NULL) AS VARCHAR) AS newest
FROM weather
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'weather'                                                      AS relation,
    'now_temp'                                                     AS measure,
    'float'                                                        AS kind,
    '-'                                                            AS unit,
    '<on-change>'                                                  AS period,
    count(now_temp)                                                AS rows,
    CAST(min(time) FILTER (WHERE now_temp IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE now_temp IS NOT NULL) AS VARCHAR) AS newest
FROM weather
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'weather'                                                        AS relation,
    'station_id'                                                     AS measure,
    'float'                                                          AS kind,
    '-'                                                              AS unit,
    '<on-change>'                                                    AS period,
    count(station_id)                                                AS rows,
    CAST(min(time) FILTER (WHERE station_id IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE station_id IS NOT NULL) AS VARCHAR) AS newest
FROM weather
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'weather'                                                     AS relation,
    'sunrise'                                                     AS measure,
    'float'                                                       AS kind,
    '-'                                                           AS unit,
    '<on-change>'                                                 AS period,
    count(sunrise)                                                AS rows,
    CAST(min(time) FILTER (WHERE sunrise IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE sunrise IS NOT NULL) AS VARCHAR) AS newest
FROM weather
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'weather'                                                    AS relation,
    'sunset'                                                     AS measure,
    'float'                                                      AS kind,
    '-'                                                          AS unit,
    '<on-change>'                                                AS period,
    count(sunset)                                                AS rows,
    CAST(min(time) FILTER (WHERE sunset IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE sunset IS NOT NULL) AS VARCHAR) AS newest
FROM weather
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'weather'                                                         AS relation,
    'temperature'                                                     AS measure,
    'float'                                                           AS kind,
    '-'                                                               AS unit,
    '<on-change>'                                                     AS period,
    count(temperature)                                                AS rows,
    CAST(min(time) FILTER (WHERE temperature IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE temperature IS NOT NULL) AS VARCHAR) AS newest
FROM weather
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'weather'                                                         AS relation,
    'uv_end_time'                                                     AS measure,
    'float'                                                           AS kind,
    '-'                                                               AS unit,
    '<on-change>'                                                     AS period,
    count(uv_end_time)                                                AS rows,
    CAST(min(time) FILTER (WHERE uv_end_time IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE uv_end_time IS NOT NULL) AS VARCHAR) AS newest
FROM weather
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'weather'                                                      AS relation,
    'uv_index'                                                     AS measure,
    'float'                                                        AS kind,
    '-'                                                            AS unit,
    '<on-change>'                                                  AS period,
    count(uv_index)                                                AS rows,
    CAST(min(time) FILTER (WHERE uv_index IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE uv_index IS NOT NULL) AS VARCHAR) AS newest
FROM weather
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'weather'                                                           AS relation,
    'uv_start_time'                                                     AS measure,
    'float'                                                             AS kind,
    '-'                                                                 AS unit,
    '<on-change>'                                                       AS period,
    count(uv_start_time)                                                AS rows,
    CAST(min(time) FILTER (WHERE uv_start_time IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE uv_start_time IS NOT NULL) AS VARCHAR) AS newest
FROM weather
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'weather'                                                           AS relation,
    'warning_count'                                                     AS measure,
    'float'                                                             AS kind,
    '-'                                                                 AS unit,
    '<on-change>'                                                       AS period,
    count(warning_count)                                                AS rows,
    CAST(min(time) FILTER (WHERE warning_count IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE warning_count IS NOT NULL) AS VARCHAR) AS newest
FROM weather
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'weather'                                                             AS relation,
    'wind_gust_speed'                                                     AS measure,
    'float'                                                               AS kind,
    '-'                                                                   AS unit,
    '<on-change>'                                                         AS period,
    count(wind_gust_speed)                                                AS rows,
    CAST(min(time) FILTER (WHERE wind_gust_speed IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE wind_gust_speed IS NOT NULL) AS VARCHAR) AS newest
FROM weather
WHERE
    module = 'homeassistant'
UNION ALL
SELECT
    'weather'                                                        AS relation,
    'wind_speed'                                                     AS measure,
    'float'                                                          AS kind,
    '-'                                                              AS unit,
    '<on-change>'                                                    AS period,
    count(wind_speed)                                                AS rows,
    CAST(min(time) FILTER (WHERE wind_speed IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE wind_speed IS NOT NULL) AS VARCHAR) AS newest
FROM weather
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
    table_name = 'weather'
    AND column_name NOT IN (
        'apparent_temperature', 'dew_point', 'entity_id', 'extended_text_str',
        'fire_danger_str', 'humidity', 'later_label_str', 'later_temp', 'module',
        'now_label_str', 'now_temp', 'precipitation_unit_str', 'pressure_unit_str',
        'short_text_str', 'state', 'station_id', 'station_name_str', 'sunrise',
        'sunrise_str', 'sunset', 'sunset_str', 'temperature', 'temperature_unit_str',
        'time', 'uv_category_str', 'uv_end_time', 'uv_end_time_str', 'uv_index',
        'uv_start_time', 'uv_start_time_str', 'visibility_unit_str', 'warning_count',
        'wind_bearing_str', 'wind_gust_speed', 'wind_speed', 'wind_speed_unit_str'
    )
ORDER BY rows DESC NULLS LAST;

-- entities
SELECT
    'automation'               AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM automation
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'binary_sensor'            AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM binary_sensor
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'binary_sensor__battery'   AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM binary_sensor__battery
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'binary_sensor__battery_charging' AS relation,
    'entity_id*'                      AS dimension,
    entity_id                         AS entity,
    '-'                               AS declared,
    count(*)                          AS rows,
    CAST(min(time) AS VARCHAR)        AS oldest,
    CAST(max(time) AS VARCHAR)        AS newest
FROM binary_sensor__battery_charging
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'binary_sensor__connectivity' AS relation,
    'entity_id*'                  AS dimension,
    entity_id                     AS entity,
    '-'                           AS declared,
    count(*)                      AS rows,
    CAST(min(time) AS VARCHAR)    AS oldest,
    CAST(max(time) AS VARCHAR)    AS newest
FROM binary_sensor__connectivity
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'binary_sensor__door'      AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM binary_sensor__door
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'binary_sensor__occupancy' AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM binary_sensor__occupancy
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'binary_sensor__safety'    AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM binary_sensor__safety
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'calendar'                 AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM calendar
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'climate'                  AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM climate
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'device_tracker'           AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM device_tracker
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'fan'                      AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM fan
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'input_boolean'            AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM input_boolean
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'light'                    AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM light
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'lock'                     AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM lock
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'media_player'             AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM media_player
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'media_player__speaker'    AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM media_player__speaker
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'media_player__tv'         AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM media_player__tv
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'number'                                    AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM number
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'person'                   AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM person
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'sensor'                                    AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
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
    'sensor__atmospheric_pressure'              AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__atmospheric_pressure
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__battery'                           AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__battery
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__carbon_dioxide'                    AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__carbon_dioxide
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
    'sensor__enum'             AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM sensor__enum
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'sensor__humidity'                          AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
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
    'sensor__pm25'                              AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__pm25
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
    'sensor__precipitation'                     AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__precipitation
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__pressure'                          AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__pressure
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__signal_strength'                   AS relation,
    'entity_id/unit_of_measurement*'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__signal_strength
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sensor__sound_pressure'                    AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__sound_pressure
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
    'sensor__timestamp'        AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM sensor__timestamp
WHERE
    module = 'homeassistant'
GROUP BY entity_id
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
    'sensor__wind_speed'                        AS relation,
    'entity_id*/unit_of_measurement'            AS dimension,
    concat(entity_id, '/', unit_of_measurement) AS entity,
    '-'                                         AS declared,
    count(*)                                    AS rows,
    CAST(min(time) AS VARCHAR)                  AS oldest,
    CAST(max(time) AS VARCHAR)                  AS newest
FROM sensor__wind_speed
WHERE
    module = 'homeassistant'
GROUP BY concat(entity_id, '/', unit_of_measurement)
UNION ALL
SELECT
    'sun'                      AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM sun
WHERE
    module = 'homeassistant'
GROUP BY entity_id
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
UNION ALL
SELECT
    'update__firmware'         AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM update__firmware
WHERE
    module = 'homeassistant'
GROUP BY entity_id
UNION ALL
SELECT
    'weather'                  AS relation,
    'entity_id*'               AS dimension,
    entity_id                  AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM weather
WHERE
    module = 'homeassistant'
GROUP BY entity_id
ORDER BY rows DESC;
