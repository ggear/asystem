--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- supervisor/host [health and utilisation of one host] every 6s
-- running_time        [float] is declared but not persisted, so it is absent by design
-- services            [bool]  is declared but not persisted, so it is absent by design
-- services_max_memory [float] is declared but not persisted, so it is absent by design
SELECT
    date_bin(INTERVAL '1 hour', time)                       AS bucket,
    host,
    avg(status)                                             AS status_fraction,
    avg(status_trend)                                       AS status_trend_fraction,
    last_value(used_processor ORDER BY time)                AS used_processor,
    last_value(used_processor_trend ORDER BY time)          AS used_processor_trend,
    last_value(used_memory ORDER BY time)                   AS used_memory,
    last_value(used_memory_trend ORDER BY time)             AS used_memory_trend,
    last_value(allocated_memory ORDER BY time)              AS allocated_memory,
    last_value(allocated_memory_trend ORDER BY time)        AS allocated_memory_trend,
    last_value(failed_log_messages ORDER BY time)           AS failed_log_messages,
    last_value(failed_log_messages_trend ORDER BY time)     AS failed_log_messages_trend,
    last_value(failed_shares ORDER BY time)                 AS failed_shares,
    last_value(failed_shares_trend ORDER BY time)           AS failed_shares_trend,
    last_value(failed_backups ORDER BY time)                AS failed_backups,
    last_value(failed_backups_trend ORDER BY time)          AS failed_backups_trend,
    last_value(warn_temperature_of_max ORDER BY time)       AS warn_temperature_of_max,
    last_value(warn_temperature_of_max_trend ORDER BY time) AS warn_temperature_of_max_trend,
    last_value(spin_fan_speed_of_max ORDER BY time)         AS spin_fan_speed_of_max,
    last_value(spin_fan_speed_of_max_trend ORDER BY time)   AS spin_fan_speed_of_max_trend,
    last_value(life_used_drives ORDER BY time)              AS life_used_drives,
    last_value(life_used_drives_trend ORDER BY time)        AS life_used_drives_trend,
    last_value(used_system_space ORDER BY time)             AS used_system_space,
    last_value(used_system_space_trend ORDER BY time)       AS used_system_space_trend,
    last_value(used_share_space ORDER BY time)              AS used_share_space,
    last_value(used_share_space_trend ORDER BY time)        AS used_share_space_trend,
    last_value(used_backup_space ORDER BY time)             AS used_backup_space,
    last_value(used_backup_space_trend ORDER BY time)       AS used_backup_space_trend,
    last_value(used_swap_space ORDER BY time)               AS used_swap_space,
    last_value(used_swap_space_trend ORDER BY time)         AS used_swap_space_trend,
    last_value(used_disk_ops ORDER BY time)                 AS used_disk_ops,
    last_value(used_disk_ops_trend ORDER BY time)           AS used_disk_ops_trend,
    last_value(used_network ORDER BY time)                  AS used_network,
    last_value(used_network_trend ORDER BY time)            AS used_network_trend,
    avg(temperature)                                        AS temperature_avg,
    min(temperature)                                        AS temperature_min,
    max(temperature)                                        AS temperature_max,
    avg(temperature_trend)                                  AS temperature_trend_avg,
    min(temperature_trend)                                  AS temperature_trend_min,
    max(temperature_trend)                                  AS temperature_trend_max
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
    AND time > now() - INTERVAL '7 days'
GROUP BY bucket, host
ORDER BY bucket, host;

-- supervisor/service [health and utilisation of one service on one host] every 6s
-- name       [str]   is declared but not persisted, so it is absent by design
-- version    [str]   is declared but not persisted, so it is absent by design
-- up_time    [float] is declared but not persisted, so it is absent by design
-- max_memory [float] is declared but not persisted, so it is absent by design
SELECT
    date_bin(INTERVAL '1 hour', time)              AS bucket,
    host,
    service,
    avg(status)                                    AS status_fraction,
    avg(status_trend)                              AS status_trend_fraction,
    avg(backup_status)                             AS backup_status_fraction,
    avg(backup_status_trend)                       AS backup_status_trend_fraction,
    avg(health_status)                             AS health_status_fraction,
    avg(health_status_trend)                       AS health_status_trend_fraction,
    avg(configured_status)                         AS configured_status_fraction,
    avg(configured_status_trend)                   AS configured_status_trend_fraction,
    last_value(used_processor ORDER BY time)       AS used_processor,
    last_value(used_processor_trend ORDER BY time) AS used_processor_trend,
    last_value(used_memory ORDER BY time)          AS used_memory,
    last_value(used_memory_trend ORDER BY time)    AS used_memory_trend,
    last_value(used_disk_ops ORDER BY time)        AS used_disk_ops,
    last_value(used_disk_ops_trend ORDER BY time)  AS used_disk_ops_trend,
    last_value(used_network ORDER BY time)         AS used_network,
    last_value(used_network_trend ORDER BY time)   AS used_network_trend,
    avg(restart_count)                             AS restart_count_avg,
    min(restart_count)                             AS restart_count_min,
    max(restart_count)                             AS restart_count_max,
    avg(restart_count_trend)                       AS restart_count_trend_avg,
    min(restart_count_trend)                       AS restart_count_trend_min,
    max(restart_count_trend)                       AS restart_count_trend_max
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NOT NULL
    AND time > now() - INTERVAL '7 days'
GROUP BY bucket, host, service
ORDER BY bucket, host, service;
