--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- every column in every measurement is declared, rows come back only on drift
SELECT
    'supervisor' AS measurement,
    column_name
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
ORDER BY column_name;

-- supervisor/host carries only its declared entities, rows come back only on drift
SELECT
    'supervisor/host' AS relation,
    host              AS entity,
    count(*)          AS rows_total
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NULL
    AND time > now() - INTERVAL '1 day'
    AND host NOT IN (
        'macmini-mad', 'macmini-max', 'macmini-may', 'macmini-meg', 'raspbpi-jen',
        'raspbpi-jil'
    )
GROUP BY host;

-- supervisor/service carries only its declared entities, rows come back only on drift
SELECT
    'supervisor/service' AS relation,
    service              AS entity,
    count(*)             AS rows_total
FROM supervisor
WHERE
    host IS NOT NULL
    AND service IS NOT NULL
    AND time > now() - INTERVAL '1 day'
    AND service NOT IN (
        'grafana', 'homeassistant', 'influxdb', 'influxdb3', 'letsencrypt', 'mariadb',
        'mlflow', 'mlserver', 'networks', 'nginx', 'openra', 'plex', 'postgres', 'sabnzbd',
        'sonarr', 'supervisor', 'tempstat', 'unpoller', 'vernemq', 'weewx', 'wrangle',
        'zigbee2mqtt'
    )
GROUP BY service;
