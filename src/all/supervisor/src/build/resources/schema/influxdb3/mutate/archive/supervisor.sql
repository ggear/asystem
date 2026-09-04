--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- an archived measure is retained deliberately with nothing to delete, silenced in verify and describe, and this reports the history it still carries
SELECT
    'supervisor'                                                         AS relation,
    'failed_backups'                                                     AS measure,
    count(failed_backups)                                                AS carried,
    CAST(min(time) FILTER (WHERE failed_backups IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE failed_backups IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
UNION ALL
SELECT
    'supervisor'                                                               AS relation,
    'failed_backups_trend'                                                     AS measure,
    count(failed_backups_trend)                                                AS carried,
    CAST(min(time) FILTER (WHERE failed_backups_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE failed_backups_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
UNION ALL
SELECT
    'supervisor'                                                           AS relation,
    'life_used_drives'                                                     AS measure,
    count(life_used_drives)                                                AS carried,
    CAST(min(time) FILTER (WHERE life_used_drives IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE life_used_drives IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
UNION ALL
SELECT
    'supervisor'                                                                 AS relation,
    'life_used_drives_trend'                                                     AS measure,
    count(life_used_drives_trend)                                                AS carried,
    CAST(min(time) FILTER (WHERE life_used_drives_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE life_used_drives_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
UNION ALL
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
    'supervisor'                                                        AS relation,
    'used_disk_ops'                                                     AS measure,
    count(used_disk_ops)                                                AS carried,
    CAST(min(time) FILTER (WHERE used_disk_ops IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_disk_ops IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
UNION ALL
SELECT
    'supervisor'                                                              AS relation,
    'used_disk_ops_trend'                                                     AS measure,
    count(used_disk_ops_trend)                                                AS carried,
    CAST(min(time) FILTER (WHERE used_disk_ops_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_disk_ops_trend IS NOT NULL) AS VARCHAR) AS newest
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
