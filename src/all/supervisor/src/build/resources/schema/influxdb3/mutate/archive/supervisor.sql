--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- an archived measure is retained deliberately with nothing to delete, silenced in verify and describe, and this reports the history it still carries
SELECT
    'supervisor'                                                                AS relation,
    'spin_fan_speed_of_max'                                                     AS measure,
    count(spin_fan_speed_of_max)                                                AS carried,
    CAST(min(time) FILTER (WHERE spin_fan_speed_of_max IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE spin_fan_speed_of_max IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
UNION ALL
SELECT
    'supervisor'                                                                      AS relation,
    'spin_fan_speed_of_max_trend'                                                     AS measure,
    count(spin_fan_speed_of_max_trend)                                                AS carried,
    CAST(min(time) FILTER (WHERE spin_fan_speed_of_max_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE spin_fan_speed_of_max_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
UNION ALL
SELECT
    'supervisor'                                                            AS relation,
    'used_system_space'                                                     AS measure,
    count(used_system_space)                                                AS carried,
    CAST(min(time) FILTER (WHERE used_system_space IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_system_space IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
UNION ALL
SELECT
    'supervisor'                                                                  AS relation,
    'used_system_space_trend'                                                     AS measure,
    count(used_system_space_trend)                                                AS carried,
    CAST(min(time) FILTER (WHERE used_system_space_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_system_space_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
UNION ALL
SELECT
    'supervisor'                                                                  AS relation,
    'warn_temperature_of_max'                                                     AS measure,
    count(warn_temperature_of_max)                                                AS carried,
    CAST(min(time) FILTER (WHERE warn_temperature_of_max IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE warn_temperature_of_max IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
UNION ALL
SELECT
    'supervisor'                                                                        AS relation,
    'warn_temperature_of_max_trend'                                                     AS measure,
    count(warn_temperature_of_max_trend)                                                AS carried,
    CAST(min(time) FILTER (WHERE warn_temperature_of_max_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE warn_temperature_of_max_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
ORDER BY measure;
