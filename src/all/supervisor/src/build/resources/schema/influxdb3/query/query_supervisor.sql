--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- supervisor/host [health and utilisation of one host] every 6s, bucketed [15 minute] across the newest two buckets
-- part 1 of 4:
SELECT
    date_bin(INTERVAL '15 minute', time)                          AS "Bucket",
    host                                                          AS "Host",
    round(avg(status), 1)                                         AS "Status Fraction",
    round(avg(status_trend), 1)                                   AS "Status Trend Fraction",
    round(last_value(used_processor ORDER BY time), 1)            AS "Used Processor",
    round(last_value(used_processor_trend ORDER BY time), 1)      AS "Used Processor Trend",
    round(last_value(used_memory ORDER BY time), 1)               AS "Used Memory",
    round(last_value(used_memory_trend ORDER BY time), 1)         AS "Used Memory Trend",
    round(last_value(allocated_memory ORDER BY time), 1)          AS "Allocated Memory",
    round(last_value(allocated_memory_trend ORDER BY time), 1)    AS "Allocated Memory Trend",
    round(last_value(failed_log_messages ORDER BY time), 1)       AS "Failed Log Messages",
    round(last_value(failed_log_messages_trend ORDER BY time), 1) AS "Failed Log Messages Trend",
    round(last_value(failed_shares ORDER BY time), 1)             AS "Failed Shares",
    round(last_value(failed_shares_trend ORDER BY time), 1)       AS "Failed Shares Trend"
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
    AND time >= now() - INTERVAL '1500 minute'
    AND time >= (SELECT max(time) FROM supervisor) - INTERVAL '15 minute'
GROUP BY "Bucket", host
ORDER BY "Bucket", host;

-- supervisor/host [health and utilisation of one host] every 6s, bucketed [15 minute] across the newest two buckets
-- part 2 of 4:
SELECT
    date_bin(INTERVAL '15 minute', time)                              AS "Bucket",
    host                                                              AS "Host",
    round(last_value(failed_backups ORDER BY time), 1)                AS "Failed Backups",
    round(last_value(failed_backups_trend ORDER BY time), 1)          AS "Failed Backups Trend",
    round(last_value(warn_temperature_of_max ORDER BY time), 1)       AS "Warn Temperature Of Max",
    round(last_value(warn_temperature_of_max_trend ORDER BY time), 1) AS "Warn Temperature Of Max Trend",
    round(last_value(spin_fan_speed_of_max ORDER BY time), 1)         AS "Spin Fan Speed Of Max",
    round(last_value(spin_fan_speed_of_max_trend ORDER BY time), 1)   AS "Spin Fan Speed Of Max Trend",
    round(last_value(life_used_drives ORDER BY time), 1)              AS "Life Used Drives",
    round(last_value(life_used_drives_trend ORDER BY time), 1)        AS "Life Used Drives Trend",
    round(last_value(used_system_space ORDER BY time), 1)             AS "Used System Space",
    round(last_value(used_system_space_trend ORDER BY time), 1)       AS "Used System Space Trend"
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
    AND time >= now() - INTERVAL '1500 minute'
    AND time >= (SELECT max(time) FROM supervisor) - INTERVAL '15 minute'
GROUP BY "Bucket", host
ORDER BY "Bucket", host;

-- supervisor/host [health and utilisation of one host] every 6s, bucketed [15 minute] across the newest two buckets
-- part 3 of 4:
SELECT
    date_bin(INTERVAL '15 minute', time)                        AS "Bucket",
    host                                                        AS "Host",
    round(last_value(used_share_space ORDER BY time), 1)        AS "Used Share Space",
    round(last_value(used_share_space_trend ORDER BY time), 1)  AS "Used Share Space Trend",
    round(last_value(used_backup_space ORDER BY time), 1)       AS "Used Backup Space",
    round(last_value(used_backup_space_trend ORDER BY time), 1) AS "Used Backup Space Trend",
    round(last_value(used_swap_space ORDER BY time), 1)         AS "Used Swap Space",
    round(last_value(used_swap_space_trend ORDER BY time), 1)   AS "Used Swap Space Trend",
    round(last_value(used_disk_ops ORDER BY time), 1)           AS "Used Disk Ops",
    round(last_value(used_disk_ops_trend ORDER BY time), 1)     AS "Used Disk Ops Trend",
    round(last_value(used_network ORDER BY time), 1)            AS "Used Network",
    round(last_value(used_network_trend ORDER BY time), 1)      AS "Used Network Trend",
    round(avg(temperature), 1)                                  AS "Temperature Avg",
    round(min(temperature), 1)                                  AS "Temperature Min"
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
    AND time >= now() - INTERVAL '1500 minute'
    AND time >= (SELECT max(time) FROM supervisor) - INTERVAL '15 minute'
GROUP BY "Bucket", host
ORDER BY "Bucket", host;

-- supervisor/host [health and utilisation of one host] every 6s, bucketed [15 minute] across the newest two buckets
-- part 4 of 4:
SELECT
    date_bin(INTERVAL '15 minute', time) AS "Bucket",
    host                                 AS "Host",
    round(max(temperature), 1)           AS "Temperature Max",
    round(avg(temperature_trend), 1)     AS "Temperature Trend Avg",
    round(min(temperature_trend), 1)     AS "Temperature Trend Min",
    round(max(temperature_trend), 1)     AS "Temperature Trend Max"
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
    AND time >= now() - INTERVAL '1500 minute'
    AND time >= (SELECT max(time) FROM supervisor) - INTERVAL '15 minute'
GROUP BY "Bucket", host
ORDER BY "Bucket", host;

-- supervisor/service [health and utilisation of one service on one host] every 6s, bucketed [15 minute] across the newest two buckets
-- part 1 of 3:
SELECT
    date_bin(INTERVAL '15 minute', time)               AS "Bucket",
    host                                               AS "Host",
    service                                            AS "Service",
    round(avg(status), 1)                              AS "Status Fraction",
    round(avg(status_trend), 1)                        AS "Status Trend Fraction",
    round(avg(backup_status), 1)                       AS "Backup Status Fraction",
    round(avg(backup_status_trend), 1)                 AS "Backup Status Trend Fraction",
    round(avg(health_status), 1)                       AS "Health Status Fraction",
    round(avg(health_status_trend), 1)                 AS "Health Status Trend Fraction",
    round(avg(configured_status), 1)                   AS "Configured Status Fraction",
    round(avg(configured_status_trend), 1)             AS "Configured Status Trend Fraction",
    round(last_value(used_processor ORDER BY time), 1) AS "Used Processor"
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
    AND time >= now() - INTERVAL '1500 minute'
    AND time >= (SELECT max(time) FROM supervisor) - INTERVAL '15 minute'
GROUP BY "Bucket", host, service
ORDER BY "Bucket", host, service;

-- supervisor/service [health and utilisation of one service on one host] every 6s, bucketed [15 minute] across the newest two buckets
-- part 2 of 3:
SELECT
    date_bin(INTERVAL '15 minute', time)                     AS "Bucket",
    host                                                     AS "Host",
    service                                                  AS "Service",
    round(last_value(used_processor_trend ORDER BY time), 1) AS "Used Processor Trend",
    round(last_value(used_memory ORDER BY time), 1)          AS "Used Memory",
    round(last_value(used_memory_trend ORDER BY time), 1)    AS "Used Memory Trend",
    round(last_value(used_disk_ops ORDER BY time), 1)        AS "Used Disk Ops",
    round(last_value(used_disk_ops_trend ORDER BY time), 1)  AS "Used Disk Ops Trend",
    round(last_value(used_network ORDER BY time), 1)         AS "Used Network",
    round(last_value(used_network_trend ORDER BY time), 1)   AS "Used Network Trend",
    round(avg(restart_count), 1)                             AS "Restart Count Avg",
    round(min(restart_count), 1)                             AS "Restart Count Min",
    round(max(restart_count), 1)                             AS "Restart Count Max",
    round(avg(restart_count_trend), 1)                       AS "Restart Count Trend Avg"
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
    AND time >= now() - INTERVAL '1500 minute'
    AND time >= (SELECT max(time) FROM supervisor) - INTERVAL '15 minute'
GROUP BY "Bucket", host, service
ORDER BY "Bucket", host, service;

-- supervisor/service [health and utilisation of one service on one host] every 6s, bucketed [15 minute] across the newest two buckets
-- part 3 of 3:
SELECT
    date_bin(INTERVAL '15 minute', time) AS "Bucket",
    host                                 AS "Host",
    service                              AS "Service",
    round(min(restart_count_trend), 1)   AS "Restart Count Trend Min",
    round(max(restart_count_trend), 1)   AS "Restart Count Trend Max"
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
    AND time >= now() - INTERVAL '1500 minute'
    AND time >= (SELECT max(time) FROM supervisor) - INTERVAL '15 minute'
GROUP BY "Bucket", host, service
ORDER BY "Bucket", host, service;
