--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- dimensions
SELECT
    'supervisor/host'    AS relation,
    'host*'              AS dimension,
    '6s'                 AS cadence,
    37                   AS measures,
    34                   AS persisted,
    '6'                  AS declared,
    count(DISTINCT host) AS observed,
    count(*)             AS rows,
    min(time)            AS oldest,
    max(time)            AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/service'    AS relation,
    'host/service*'         AS dimension,
    '6s'                    AS cadence,
    22                      AS measures,
    18                      AS persisted,
    '22'                    AS declared,
    count(DISTINCT service) AS observed,
    count(*)                AS rows,
    min(time)               AS oldest,
    max(time)               AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NOT NULL
ORDER BY relation;

-- measures
SELECT
    'supervisor/host'                                            AS relation,
    'status'                                                     AS measure,
    'bool'                                                       AS kind,
    'state'                                                      AS unit,
    '-'                                                          AS period,
    'yes'                                                        AS persisted,
    CASE WHEN count(status) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(status) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE status IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE status IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                  AS relation,
    'status_trend'                                                     AS measure,
    'bool'                                                             AS kind,
    'state'                                                            AS unit,
    '-'                                                                AS period,
    'yes'                                                              AS persisted,
    CASE WHEN count(status_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(status_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE status_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE status_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                    AS relation,
    'used_processor'                                                     AS measure,
    'int'                                                                AS kind,
    'percent'                                                            AS unit,
    '-'                                                                  AS period,
    'yes'                                                                AS persisted,
    CASE WHEN count(used_processor) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_processor) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_processor IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_processor IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                          AS relation,
    'used_processor_trend'                                                     AS measure,
    'int'                                                                      AS kind,
    'percent'                                                                  AS unit,
    '-'                                                                        AS period,
    'yes'                                                                      AS persisted,
    CASE WHEN count(used_processor_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_processor_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_processor_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_processor_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                 AS relation,
    'used_memory'                                                     AS measure,
    'int'                                                             AS kind,
    'percent'                                                         AS unit,
    '-'                                                               AS period,
    'yes'                                                             AS persisted,
    CASE WHEN count(used_memory) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_memory) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_memory IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_memory IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                       AS relation,
    'used_memory_trend'                                                     AS measure,
    'int'                                                                   AS kind,
    'percent'                                                               AS unit,
    '-'                                                                     AS period,
    'yes'                                                                   AS persisted,
    CASE WHEN count(used_memory_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_memory_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_memory_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_memory_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                      AS relation,
    'allocated_memory'                                                     AS measure,
    'int'                                                                  AS kind,
    'percent'                                                              AS unit,
    '-'                                                                    AS period,
    'yes'                                                                  AS persisted,
    CASE WHEN count(allocated_memory) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(allocated_memory) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE allocated_memory IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE allocated_memory IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                            AS relation,
    'allocated_memory_trend'                                                     AS measure,
    'int'                                                                        AS kind,
    'percent'                                                                    AS unit,
    '-'                                                                          AS period,
    'yes'                                                                        AS persisted,
    CASE WHEN count(allocated_memory_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(allocated_memory_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE allocated_memory_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE allocated_memory_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                         AS relation,
    'failed_log_messages'                                                     AS measure,
    'int'                                                                     AS kind,
    'count'                                                                   AS unit,
    '-'                                                                       AS period,
    'yes'                                                                     AS persisted,
    CASE WHEN count(failed_log_messages) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(failed_log_messages) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE failed_log_messages IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE failed_log_messages IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                               AS relation,
    'failed_log_messages_trend'                                                     AS measure,
    'int'                                                                           AS kind,
    'count'                                                                         AS unit,
    '-'                                                                             AS period,
    'yes'                                                                           AS persisted,
    CASE WHEN count(failed_log_messages_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(failed_log_messages_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE failed_log_messages_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE failed_log_messages_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                   AS relation,
    'failed_shares'                                                     AS measure,
    'int'                                                               AS kind,
    'count'                                                             AS unit,
    '-'                                                                 AS period,
    'yes'                                                               AS persisted,
    CASE WHEN count(failed_shares) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(failed_shares) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE failed_shares IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE failed_shares IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                         AS relation,
    'failed_shares_trend'                                                     AS measure,
    'int'                                                                     AS kind,
    'count'                                                                   AS unit,
    '-'                                                                       AS period,
    'yes'                                                                     AS persisted,
    CASE WHEN count(failed_shares_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(failed_shares_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE failed_shares_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE failed_shares_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                    AS relation,
    'failed_backups'                                                     AS measure,
    'int'                                                                AS kind,
    'count'                                                              AS unit,
    '-'                                                                  AS period,
    'yes'                                                                AS persisted,
    CASE WHEN count(failed_backups) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(failed_backups) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE failed_backups IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE failed_backups IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                          AS relation,
    'failed_backups_trend'                                                     AS measure,
    'int'                                                                      AS kind,
    'count'                                                                    AS unit,
    '-'                                                                        AS period,
    'yes'                                                                      AS persisted,
    CASE WHEN count(failed_backups_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(failed_backups_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE failed_backups_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE failed_backups_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                             AS relation,
    'warn_temperature_of_max'                                                     AS measure,
    'int'                                                                         AS kind,
    'percent'                                                                     AS unit,
    '-'                                                                           AS period,
    'yes'                                                                         AS persisted,
    CASE WHEN count(warn_temperature_of_max) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(warn_temperature_of_max) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE warn_temperature_of_max IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE warn_temperature_of_max IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                                   AS relation,
    'warn_temperature_of_max_trend'                                                     AS measure,
    'int'                                                                               AS kind,
    'percent'                                                                           AS unit,
    '-'                                                                                 AS period,
    'yes'                                                                               AS persisted,
    CASE WHEN count(warn_temperature_of_max_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(warn_temperature_of_max_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE warn_temperature_of_max_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE warn_temperature_of_max_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                           AS relation,
    'spin_fan_speed_of_max'                                                     AS measure,
    'int'                                                                       AS kind,
    'percent'                                                                   AS unit,
    '-'                                                                         AS period,
    'yes'                                                                       AS persisted,
    CASE WHEN count(spin_fan_speed_of_max) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(spin_fan_speed_of_max) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE spin_fan_speed_of_max IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE spin_fan_speed_of_max IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                                 AS relation,
    'spin_fan_speed_of_max_trend'                                                     AS measure,
    'int'                                                                             AS kind,
    'percent'                                                                         AS unit,
    '-'                                                                               AS period,
    'yes'                                                                             AS persisted,
    CASE WHEN count(spin_fan_speed_of_max_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(spin_fan_speed_of_max_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE spin_fan_speed_of_max_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE spin_fan_speed_of_max_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                      AS relation,
    'life_used_drives'                                                     AS measure,
    'int'                                                                  AS kind,
    'percent'                                                              AS unit,
    '-'                                                                    AS period,
    'yes'                                                                  AS persisted,
    CASE WHEN count(life_used_drives) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(life_used_drives) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE life_used_drives IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE life_used_drives IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                            AS relation,
    'life_used_drives_trend'                                                     AS measure,
    'int'                                                                        AS kind,
    'percent'                                                                    AS unit,
    '-'                                                                          AS period,
    'yes'                                                                        AS persisted,
    CASE WHEN count(life_used_drives_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(life_used_drives_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE life_used_drives_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE life_used_drives_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                       AS relation,
    'used_system_space'                                                     AS measure,
    'int'                                                                   AS kind,
    'percent'                                                               AS unit,
    '-'                                                                     AS period,
    'yes'                                                                   AS persisted,
    CASE WHEN count(used_system_space) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_system_space) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_system_space IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_system_space IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                             AS relation,
    'used_system_space_trend'                                                     AS measure,
    'int'                                                                         AS kind,
    'percent'                                                                     AS unit,
    '-'                                                                           AS period,
    'yes'                                                                         AS persisted,
    CASE WHEN count(used_system_space_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_system_space_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_system_space_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_system_space_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                      AS relation,
    'used_share_space'                                                     AS measure,
    'int'                                                                  AS kind,
    'percent'                                                              AS unit,
    '-'                                                                    AS period,
    'yes'                                                                  AS persisted,
    CASE WHEN count(used_share_space) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_share_space) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_share_space IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_share_space IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                            AS relation,
    'used_share_space_trend'                                                     AS measure,
    'int'                                                                        AS kind,
    'percent'                                                                    AS unit,
    '-'                                                                          AS period,
    'yes'                                                                        AS persisted,
    CASE WHEN count(used_share_space_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_share_space_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_share_space_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_share_space_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                       AS relation,
    'used_backup_space'                                                     AS measure,
    'int'                                                                   AS kind,
    'percent'                                                               AS unit,
    '-'                                                                     AS period,
    'yes'                                                                   AS persisted,
    CASE WHEN count(used_backup_space) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_backup_space) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_backup_space IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_backup_space IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                             AS relation,
    'used_backup_space_trend'                                                     AS measure,
    'int'                                                                         AS kind,
    'percent'                                                                     AS unit,
    '-'                                                                           AS period,
    'yes'                                                                         AS persisted,
    CASE WHEN count(used_backup_space_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_backup_space_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_backup_space_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_backup_space_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                     AS relation,
    'used_swap_space'                                                     AS measure,
    'int'                                                                 AS kind,
    'percent'                                                             AS unit,
    '-'                                                                   AS period,
    'yes'                                                                 AS persisted,
    CASE WHEN count(used_swap_space) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_swap_space) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_swap_space IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_swap_space IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                           AS relation,
    'used_swap_space_trend'                                                     AS measure,
    'int'                                                                       AS kind,
    'percent'                                                                   AS unit,
    '-'                                                                         AS period,
    'yes'                                                                       AS persisted,
    CASE WHEN count(used_swap_space_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_swap_space_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_swap_space_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_swap_space_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                   AS relation,
    'used_disk_ops'                                                     AS measure,
    'int'                                                               AS kind,
    'percent'                                                           AS unit,
    '-'                                                                 AS period,
    'yes'                                                               AS persisted,
    CASE WHEN count(used_disk_ops) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_disk_ops) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_disk_ops IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_disk_ops IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                         AS relation,
    'used_disk_ops_trend'                                                     AS measure,
    'int'                                                                     AS kind,
    'percent'                                                                 AS unit,
    '-'                                                                       AS period,
    'yes'                                                                     AS persisted,
    CASE WHEN count(used_disk_ops_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_disk_ops_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_disk_ops_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_disk_ops_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                  AS relation,
    'used_network'                                                     AS measure,
    'int'                                                              AS kind,
    'percent'                                                          AS unit,
    '-'                                                                AS period,
    'yes'                                                              AS persisted,
    CASE WHEN count(used_network) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_network) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_network IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_network IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                        AS relation,
    'used_network_trend'                                                     AS measure,
    'int'                                                                    AS kind,
    'percent'                                                                AS unit,
    '-'                                                                      AS period,
    'yes'                                                                    AS persisted,
    CASE WHEN count(used_network_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_network_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_network_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_network_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'running_time'    AS measure,
    'float'           AS kind,
    'seconds'         AS unit,
    '-'               AS period,
    'no'              AS persisted,
    'no'              AS observed,
    '-'               AS rows,
    '-'               AS oldest,
    '-'               AS newest
FROM (VALUES (1)) AS placeholder(one)
UNION ALL
SELECT
    'supervisor/host'                                                 AS relation,
    'temperature'                                                     AS measure,
    'float'                                                           AS kind,
    'celsius'                                                         AS unit,
    '-'                                                               AS period,
    'yes'                                                             AS persisted,
    CASE WHEN count(temperature) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(temperature) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE temperature IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE temperature IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host'                                                       AS relation,
    'temperature_trend'                                                     AS measure,
    'float'                                                                 AS kind,
    'celsius'                                                               AS unit,
    '-'                                                                     AS period,
    'yes'                                                                   AS persisted,
    CASE WHEN count(temperature_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(temperature_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE temperature_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE temperature_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'services'        AS measure,
    'bool'            AS kind,
    'state'           AS unit,
    '-'               AS period,
    'no'              AS persisted,
    'no'              AS observed,
    '-'               AS rows,
    '-'               AS oldest,
    '-'               AS newest
FROM (VALUES (1)) AS placeholder(one)
UNION ALL
SELECT
    'supervisor/host'     AS relation,
    'services_max_memory' AS measure,
    'float'               AS kind,
    'megabytes'           AS unit,
    '-'                   AS period,
    'no'                  AS persisted,
    'no'                  AS observed,
    '-'                   AS rows,
    '-'                   AS oldest,
    '-'                   AS newest
FROM (VALUES (1)) AS placeholder(one)
UNION ALL
SELECT
    'supervisor/service'                                         AS relation,
    'status'                                                     AS measure,
    'bool'                                                       AS kind,
    'state'                                                      AS unit,
    '-'                                                          AS period,
    'yes'                                                        AS persisted,
    CASE WHEN count(status) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(status) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE status IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE status IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                               AS relation,
    'status_trend'                                                     AS measure,
    'bool'                                                             AS kind,
    'state'                                                            AS unit,
    '-'                                                                AS period,
    'yes'                                                              AS persisted,
    CASE WHEN count(status_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(status_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE status_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE status_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                AS relation,
    'backup_status'                                                     AS measure,
    'bool'                                                              AS kind,
    'state'                                                             AS unit,
    '-'                                                                 AS period,
    'yes'                                                               AS persisted,
    CASE WHEN count(backup_status) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(backup_status) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE backup_status IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE backup_status IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                      AS relation,
    'backup_status_trend'                                                     AS measure,
    'bool'                                                                    AS kind,
    'state'                                                                   AS unit,
    '-'                                                                       AS period,
    'yes'                                                                     AS persisted,
    CASE WHEN count(backup_status_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(backup_status_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE backup_status_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE backup_status_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                AS relation,
    'health_status'                                                     AS measure,
    'bool'                                                              AS kind,
    'state'                                                             AS unit,
    '-'                                                                 AS period,
    'yes'                                                               AS persisted,
    CASE WHEN count(health_status) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(health_status) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE health_status IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE health_status IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                      AS relation,
    'health_status_trend'                                                     AS measure,
    'bool'                                                                    AS kind,
    'state'                                                                   AS unit,
    '-'                                                                       AS period,
    'yes'                                                                     AS persisted,
    CASE WHEN count(health_status_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(health_status_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE health_status_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE health_status_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                    AS relation,
    'configured_status'                                                     AS measure,
    'bool'                                                                  AS kind,
    'state'                                                                 AS unit,
    '-'                                                                     AS period,
    'yes'                                                                   AS persisted,
    CASE WHEN count(configured_status) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(configured_status) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE configured_status IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE configured_status IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                          AS relation,
    'configured_status_trend'                                                     AS measure,
    'bool'                                                                        AS kind,
    'state'                                                                       AS unit,
    '-'                                                                           AS period,
    'yes'                                                                         AS persisted,
    CASE WHEN count(configured_status_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(configured_status_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE configured_status_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE configured_status_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'name'               AS measure,
    'str'                AS kind,
    'text'               AS unit,
    '-'                  AS period,
    'no'                 AS persisted,
    'no'                 AS observed,
    '-'                  AS rows,
    '-'                  AS oldest,
    '-'                  AS newest
FROM (VALUES (1)) AS placeholder(one)
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'version'            AS measure,
    'str'                AS kind,
    'text'               AS unit,
    '-'                  AS period,
    'no'                 AS persisted,
    'no'                 AS observed,
    '-'                  AS rows,
    '-'                  AS oldest,
    '-'                  AS newest
FROM (VALUES (1)) AS placeholder(one)
UNION ALL
SELECT
    'supervisor/service'                                                 AS relation,
    'used_processor'                                                     AS measure,
    'int'                                                                AS kind,
    'percent'                                                            AS unit,
    '-'                                                                  AS period,
    'yes'                                                                AS persisted,
    CASE WHEN count(used_processor) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_processor) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_processor IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_processor IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                       AS relation,
    'used_processor_trend'                                                     AS measure,
    'int'                                                                      AS kind,
    'percent'                                                                  AS unit,
    '-'                                                                        AS period,
    'yes'                                                                      AS persisted,
    CASE WHEN count(used_processor_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_processor_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_processor_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_processor_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                              AS relation,
    'used_memory'                                                     AS measure,
    'int'                                                             AS kind,
    'percent'                                                         AS unit,
    '-'                                                               AS period,
    'yes'                                                             AS persisted,
    CASE WHEN count(used_memory) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_memory) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_memory IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_memory IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                    AS relation,
    'used_memory_trend'                                                     AS measure,
    'int'                                                                   AS kind,
    'percent'                                                               AS unit,
    '-'                                                                     AS period,
    'yes'                                                                   AS persisted,
    CASE WHEN count(used_memory_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_memory_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_memory_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_memory_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                AS relation,
    'used_disk_ops'                                                     AS measure,
    'int'                                                               AS kind,
    'percent'                                                           AS unit,
    '-'                                                                 AS period,
    'yes'                                                               AS persisted,
    CASE WHEN count(used_disk_ops) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_disk_ops) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_disk_ops IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_disk_ops IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                      AS relation,
    'used_disk_ops_trend'                                                     AS measure,
    'int'                                                                     AS kind,
    'percent'                                                                 AS unit,
    '-'                                                                       AS period,
    'yes'                                                                     AS persisted,
    CASE WHEN count(used_disk_ops_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_disk_ops_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_disk_ops_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_disk_ops_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                               AS relation,
    'used_network'                                                     AS measure,
    'int'                                                              AS kind,
    'percent'                                                          AS unit,
    '-'                                                                AS period,
    'yes'                                                              AS persisted,
    CASE WHEN count(used_network) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_network) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_network IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_network IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                     AS relation,
    'used_network_trend'                                                     AS measure,
    'int'                                                                    AS kind,
    'percent'                                                                AS unit,
    '-'                                                                      AS period,
    'yes'                                                                    AS persisted,
    CASE WHEN count(used_network_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(used_network_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE used_network_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE used_network_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'up_time'            AS measure,
    'float'              AS kind,
    'seconds'            AS unit,
    '-'                  AS period,
    'no'                 AS persisted,
    'no'                 AS observed,
    '-'                  AS rows,
    '-'                  AS oldest,
    '-'                  AS newest
FROM (VALUES (1)) AS placeholder(one)
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'max_memory'         AS measure,
    'float'              AS kind,
    'megabytes'          AS unit,
    '-'                  AS period,
    'no'                 AS persisted,
    'no'                 AS observed,
    '-'                  AS rows,
    '-'                  AS oldest,
    '-'                  AS newest
FROM (VALUES (1)) AS placeholder(one)
UNION ALL
SELECT
    'supervisor/service'                                                AS relation,
    'restart_count'                                                     AS measure,
    'float'                                                             AS kind,
    'count'                                                             AS unit,
    '-'                                                                 AS period,
    'yes'                                                               AS persisted,
    CASE WHEN count(restart_count) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(restart_count) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE restart_count IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE restart_count IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    'supervisor/service'                                                      AS relation,
    'restart_count_trend'                                                     AS measure,
    'float'                                                                   AS kind,
    'count'                                                                   AS unit,
    '-'                                                                       AS period,
    'yes'                                                                     AS persisted,
    CASE WHEN count(restart_count_trend) > 0 THEN 'yes' ELSE 'no' END         AS observed,
    CAST(count(restart_count_trend) AS VARCHAR)                               AS rows,
    CAST(min(time) FILTER (WHERE restart_count_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE restart_count_trend IS NOT NULL) AS VARCHAR) AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NOT NULL
UNION ALL
SELECT
    '-'         AS relation,
    column_name AS measure,
    '-'         AS kind,
    '-'         AS unit,
    '-'         AS period,
    '-'         AS persisted,
    'yes'       AS observed,
    '-'         AS rows,
    '-'         AS oldest,
    '-'         AS newest
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
    AND column_name NOT IN (
        'allocated_memory', 'allocated_memory_trend', 'backup_status',
        'backup_status_trend', 'configured_status', 'configured_status_trend',
        'failed_backups', 'failed_backups_trend', 'failed_log_messages',
        'failed_log_messages_trend', 'failed_shares', 'failed_shares_trend',
        'health_status', 'health_status_trend', 'host', 'life_used_drives',
        'life_used_drives_trend', 'max_memory', 'name', 'restart_count',
        'restart_count_trend', 'running_time', 'service', 'services', 'services_max_memory',
        'spin_fan_speed_of_max', 'spin_fan_speed_of_max_trend', 'status', 'status_trend',
        'temperature', 'temperature_trend', 'time', 'up_time', 'used_backup_space',
        'used_backup_space_trend', 'used_disk_ops', 'used_disk_ops_trend', 'used_memory',
        'used_memory_trend', 'used_network', 'used_network_trend', 'used_processor',
        'used_processor_trend', 'used_share_space', 'used_share_space_trend',
        'used_swap_space', 'used_swap_space_trend', 'used_system_space',
        'used_system_space_trend', 'version', 'warn_temperature_of_max',
        'warn_temperature_of_max_trend'
    )
ORDER BY relation, measure;

-- entities
SELECT
    'supervisor/host' AS relation,
    'host*'           AS dimension,
    host              AS entity,
    CASE WHEN host IN (
        'macmini-mad', 'macmini-max', 'macmini-may', 'macmini-meg', 'raspbpi-jen',
        'raspbpi-jil'
    ) THEN 'yes' ELSE 'no' END AS declared,
    count(*)          AS rows,
    min(time)         AS oldest,
    max(time)         AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
GROUP BY host, CASE WHEN host IN (
    'macmini-mad', 'macmini-max', 'macmini-may', 'macmini-meg', 'raspbpi-jen',
    'raspbpi-jil'
) THEN 'yes' ELSE 'no' END
UNION ALL
SELECT
    'supervisor/service'       AS relation,
    'host/service*'            AS dimension,
    concat(host, '/', service) AS entity,
    CASE WHEN service IN (
        'grafana', 'homeassistant', 'influxdb', 'influxdb3', 'letsencrypt', 'mariadb',
        'mlflow', 'mlserver', 'networks', 'nginx', 'openra', 'plex', 'postgres', 'sabnzbd',
        'sonarr', 'supervisor', 'tempstat', 'unpoller', 'vernemq', 'weewx', 'wrangle',
        'zigbee2mqtt'
    ) THEN 'yes' ELSE 'no' END AS declared,
    count(*)                   AS rows,
    min(time)                  AS oldest,
    max(time)                  AS newest
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NOT NULL
GROUP BY concat(host, '/', service), CASE WHEN service IN (
    'grafana', 'homeassistant', 'influxdb', 'influxdb3', 'letsencrypt', 'mariadb',
    'mlflow', 'mlserver', 'networks', 'nginx', 'openra', 'plex', 'postgres', 'sabnzbd',
    'sonarr', 'supervisor', 'tempstat', 'unpoller', 'vernemq', 'weewx', 'wrangle',
    'zigbee2mqtt'
) THEN 'yes' ELSE 'no' END
ORDER BY relation, entity;
