--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- declared vocabulary against what the service actually wrote, rows come back only on drift
SELECT
    'supervisor/host' AS relation,
    'status'          AS measure,
    '6s'              AS period,
    'state'           AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'status') = 0
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'status_trend'    AS measure,
    '6s'              AS period,
    'state'           AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'status_trend') = 0
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'used_processor'  AS measure,
    '6s'              AS period,
    'percent'         AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_processor') = 0
UNION ALL
SELECT
    'supervisor/host'      AS relation,
    'used_processor_trend' AS measure,
    '6s'                   AS period,
    'percent'              AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_processor_trend') = 0
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'used_memory'     AS measure,
    '6s'              AS period,
    'percent'         AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_memory') = 0
UNION ALL
SELECT
    'supervisor/host'   AS relation,
    'used_memory_trend' AS measure,
    '6s'                AS period,
    'percent'           AS unit,
    'missing'           AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_memory_trend') = 0
UNION ALL
SELECT
    'supervisor/host'  AS relation,
    'allocated_memory' AS measure,
    '6s'               AS period,
    'percent'          AS unit,
    'missing'          AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'allocated_memory') = 0
UNION ALL
SELECT
    'supervisor/host'        AS relation,
    'allocated_memory_trend' AS measure,
    '6s'                     AS period,
    'percent'                AS unit,
    'missing'                AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'allocated_memory_trend') = 0
UNION ALL
SELECT
    'supervisor/host'     AS relation,
    'failed_log_messages' AS measure,
    '6s'                  AS period,
    'count'               AS unit,
    'missing'             AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'failed_log_messages') = 0
UNION ALL
SELECT
    'supervisor/host'           AS relation,
    'failed_log_messages_trend' AS measure,
    '6s'                        AS period,
    'count'                     AS unit,
    'missing'                   AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'failed_log_messages_trend') = 0
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'failed_shares'   AS measure,
    '6s'              AS period,
    'count'           AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'failed_shares') = 0
UNION ALL
SELECT
    'supervisor/host'     AS relation,
    'failed_shares_trend' AS measure,
    '6s'                  AS period,
    'count'               AS unit,
    'missing'             AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'failed_shares_trend') = 0
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'failed_backups'  AS measure,
    '6s'              AS period,
    'count'           AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'failed_backups') = 0
UNION ALL
SELECT
    'supervisor/host'      AS relation,
    'failed_backups_trend' AS measure,
    '6s'                   AS period,
    'count'                AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'failed_backups_trend') = 0
UNION ALL
SELECT
    'supervisor/host'         AS relation,
    'warn_temperature_of_max' AS measure,
    '6s'                      AS period,
    'percent'                 AS unit,
    'missing'                 AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'warn_temperature_of_max') = 0
UNION ALL
SELECT
    'supervisor/host'               AS relation,
    'warn_temperature_of_max_trend' AS measure,
    '6s'                            AS period,
    'percent'                       AS unit,
    'missing'                       AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'warn_temperature_of_max_trend') = 0
UNION ALL
SELECT
    'supervisor/host'       AS relation,
    'spin_fan_speed_of_max' AS measure,
    '6s'                    AS period,
    'percent'               AS unit,
    'missing'               AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'spin_fan_speed_of_max') = 0
UNION ALL
SELECT
    'supervisor/host'             AS relation,
    'spin_fan_speed_of_max_trend' AS measure,
    '6s'                          AS period,
    'percent'                     AS unit,
    'missing'                     AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'spin_fan_speed_of_max_trend') = 0
UNION ALL
SELECT
    'supervisor/host'  AS relation,
    'life_used_drives' AS measure,
    '6s'               AS period,
    'percent'          AS unit,
    'missing'          AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'life_used_drives') = 0
UNION ALL
SELECT
    'supervisor/host'        AS relation,
    'life_used_drives_trend' AS measure,
    '6s'                     AS period,
    'percent'                AS unit,
    'missing'                AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'life_used_drives_trend') = 0
UNION ALL
SELECT
    'supervisor/host'   AS relation,
    'used_system_space' AS measure,
    '6s'                AS period,
    'percent'           AS unit,
    'missing'           AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_system_space') = 0
UNION ALL
SELECT
    'supervisor/host'         AS relation,
    'used_system_space_trend' AS measure,
    '6s'                      AS period,
    'percent'                 AS unit,
    'missing'                 AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_system_space_trend') = 0
UNION ALL
SELECT
    'supervisor/host'  AS relation,
    'used_share_space' AS measure,
    '6s'               AS period,
    'percent'          AS unit,
    'missing'          AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_share_space') = 0
UNION ALL
SELECT
    'supervisor/host'        AS relation,
    'used_share_space_trend' AS measure,
    '6s'                     AS period,
    'percent'                AS unit,
    'missing'                AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_share_space_trend') = 0
UNION ALL
SELECT
    'supervisor/host'   AS relation,
    'used_backup_space' AS measure,
    '6s'                AS period,
    'percent'           AS unit,
    'missing'           AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_backup_space') = 0
UNION ALL
SELECT
    'supervisor/host'         AS relation,
    'used_backup_space_trend' AS measure,
    '6s'                      AS period,
    'percent'                 AS unit,
    'missing'                 AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_backup_space_trend') = 0
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'used_swap_space' AS measure,
    '6s'              AS period,
    'percent'         AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_swap_space') = 0
UNION ALL
SELECT
    'supervisor/host'       AS relation,
    'used_swap_space_trend' AS measure,
    '6s'                    AS period,
    'percent'               AS unit,
    'missing'               AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_swap_space_trend') = 0
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'used_disk_ops'   AS measure,
    '6s'              AS period,
    'percent'         AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_disk_ops') = 0
UNION ALL
SELECT
    'supervisor/host'     AS relation,
    'used_disk_ops_trend' AS measure,
    '6s'                  AS period,
    'percent'             AS unit,
    'missing'             AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_disk_ops_trend') = 0
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'used_network'    AS measure,
    '6s'              AS period,
    'percent'         AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_network') = 0
UNION ALL
SELECT
    'supervisor/host'    AS relation,
    'used_network_trend' AS measure,
    '6s'                 AS period,
    'percent'            AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_network_trend') = 0
UNION ALL
SELECT
    'supervisor/host' AS relation,
    'temperature'     AS measure,
    '6s'              AS period,
    'celsius'         AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'temperature') = 0
UNION ALL
SELECT
    'supervisor/host'   AS relation,
    'temperature_trend' AS measure,
    '6s'                AS period,
    'celsius'           AS unit,
    'missing'           AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'temperature_trend') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'status'             AS measure,
    '6s'                 AS period,
    'state'              AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'status') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'status_trend'       AS measure,
    '6s'                 AS period,
    'state'              AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'status_trend') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'backup_status'      AS measure,
    '6s'                 AS period,
    'state'              AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'backup_status') = 0
UNION ALL
SELECT
    'supervisor/service'  AS relation,
    'backup_status_trend' AS measure,
    '6s'                  AS period,
    'state'               AS unit,
    'missing'             AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'backup_status_trend') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'health_status'      AS measure,
    '6s'                 AS period,
    'state'              AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'health_status') = 0
UNION ALL
SELECT
    'supervisor/service'  AS relation,
    'health_status_trend' AS measure,
    '6s'                  AS period,
    'state'               AS unit,
    'missing'             AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'health_status_trend') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'configured_status'  AS measure,
    '6s'                 AS period,
    'state'              AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'configured_status') = 0
UNION ALL
SELECT
    'supervisor/service'      AS relation,
    'configured_status_trend' AS measure,
    '6s'                      AS period,
    'state'                   AS unit,
    'missing'                 AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'configured_status_trend') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'used_processor'     AS measure,
    '6s'                 AS period,
    'percent'            AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_processor') = 0
UNION ALL
SELECT
    'supervisor/service'   AS relation,
    'used_processor_trend' AS measure,
    '6s'                   AS period,
    'percent'              AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_processor_trend') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'used_memory'        AS measure,
    '6s'                 AS period,
    'percent'            AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_memory') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'used_memory_trend'  AS measure,
    '6s'                 AS period,
    'percent'            AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_memory_trend') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'used_disk_ops'      AS measure,
    '6s'                 AS period,
    'percent'            AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_disk_ops') = 0
UNION ALL
SELECT
    'supervisor/service'  AS relation,
    'used_disk_ops_trend' AS measure,
    '6s'                  AS period,
    'percent'             AS unit,
    'missing'             AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_disk_ops_trend') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'used_network'       AS measure,
    '6s'                 AS period,
    'percent'            AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_network') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'used_network_trend' AS measure,
    '6s'                 AS period,
    'percent'            AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'used_network_trend') = 0
UNION ALL
SELECT
    'supervisor/service' AS relation,
    'restart_count'      AS measure,
    '6s'                 AS period,
    'count'              AS unit,
    'missing'            AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'restart_count') = 0
UNION ALL
SELECT
    'supervisor/service'  AS relation,
    'restart_count_trend' AS measure,
    '6s'                  AS period,
    'count'               AS unit,
    'missing'             AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
HAVING count(*) FILTER (WHERE column_name = 'restart_count_trend') = 0
UNION ALL
SELECT
    'supervisor' AS relation,
    column_name  AS measure,
    '-'          AS period,
    '-'          AS unit,
    'undeclared' AS fault
FROM information_schema.columns
WHERE
    table_name = 'supervisor'
    AND column_name NOT IN (
        'allocated_memory', 'allocated_memory_trend', 'backup_status',
        'backup_status_trend', 'configured_status', 'configured_status_trend',
        'failed_backups', 'failed_backups_trend', 'failed_log_messages',
        'failed_log_messages_trend', 'failed_shares', 'failed_shares_trend',
        'health_status', 'health_status_trend', 'host', 'life_used_drives',
        'life_used_drives_trend', 'restart_count', 'restart_count_trend', 'service',
        'spin_fan_speed_of_max', 'spin_fan_speed_of_max_trend', 'status', 'status_trend',
        'temperature', 'temperature_trend', 'time', 'used_backup_space',
        'used_backup_space_trend', 'used_disk_ops', 'used_disk_ops_trend', 'used_memory',
        'used_memory_trend', 'used_network', 'used_network_trend', 'used_processor',
        'used_processor_trend', 'used_share_space', 'used_share_space_trend',
        'used_swap_space', 'used_swap_space_trend', 'used_system_space',
        'used_system_space_trend', 'warn_temperature_of_max',
        'warn_temperature_of_max_trend'
    )
ORDER BY fault, measure;
