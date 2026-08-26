--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- supervisor/host [health and utilisation of one host] every 6s, bucketed [15 minute] across the newest two buckets
-- part 1 of 18:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(avg(status), 1)                                        AS "Status Fraction",
    count(status)                                                AS "Status Count",
    count(DISTINCT status)                                       AS "Status Distinct",
    round(avg(status_trend), 1)                                  AS "Status Trend Fraction",
    count(status_trend)                                          AS "Status Trend Count",
    count(DISTINCT status_trend)                                 AS "Status Trend Distinct",
    round(last_value(used_processor ORDER BY time), 1)           AS "Used Processor",
    count(used_processor)                                        AS "Used Processor Count",
    count(DISTINCT used_processor)                               AS "Used Processor Distinct"
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
-- part 2 of 18:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(last_value(used_processor_trend ORDER BY time), 1)     AS "Used Processor Trend",
    count(used_processor_trend)                                  AS "Used Processor Trend Count",
    count(DISTINCT used_processor_trend)                         AS "Used Processor Trend Distinct",
    round(last_value(used_memory ORDER BY time), 1)              AS "Used Memory",
    count(used_memory)                                           AS "Used Memory Count",
    count(DISTINCT used_memory)                                  AS "Used Memory Distinct"
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
-- part 3 of 18:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(last_value(used_memory_trend ORDER BY time), 1)        AS "Used Memory Trend",
    count(used_memory_trend)                                     AS "Used Memory Trend Count",
    count(DISTINCT used_memory_trend)                            AS "Used Memory Trend Distinct",
    round(last_value(allocated_memory ORDER BY time), 1)         AS "Allocated Memory",
    count(allocated_memory)                                      AS "Allocated Memory Count",
    count(DISTINCT allocated_memory)                             AS "Allocated Memory Distinct"
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
-- part 4 of 18:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(last_value(allocated_memory_trend ORDER BY time), 1)   AS "Allocated Memory Trend",
    count(allocated_memory_trend)                                AS "Allocated Memory Trend Count",
    count(DISTINCT allocated_memory_trend)                       AS "Allocated Memory Trend Distinct",
    round(last_value(failed_log_messages ORDER BY time), 1)      AS "Failed Log Messages",
    count(failed_log_messages)                                   AS "Failed Log Messages Count",
    count(DISTINCT failed_log_messages)                          AS "Failed Log Messages Distinct"
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
-- part 5 of 18:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute')  AS "Bucket",
    host                                                          AS "Host",
    count(*)                                                      AS "Rows",
    min(time) + INTERVAL '480 minute'                             AS "Oldest",
    max(time) + INTERVAL '480 minute'                             AS "Newest",
    round(last_value(failed_log_messages_trend ORDER BY time), 1) AS "Failed Log Messages Trend",
    count(failed_log_messages_trend)                              AS "Failed Log Messages Trend Count",
    count(DISTINCT failed_log_messages_trend)                     AS "Failed Log Messages Trend Distinct",
    round(last_value(failed_shares ORDER BY time), 1)             AS "Failed Shares",
    count(failed_shares)                                          AS "Failed Shares Count",
    count(DISTINCT failed_shares)                                 AS "Failed Shares Distinct"
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
-- part 6 of 18:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(last_value(failed_shares_trend ORDER BY time), 1)      AS "Failed Shares Trend",
    count(failed_shares_trend)                                   AS "Failed Shares Trend Count",
    count(DISTINCT failed_shares_trend)                          AS "Failed Shares Trend Distinct",
    round(last_value(failed_backups ORDER BY time), 1)           AS "Failed Backups",
    count(failed_backups)                                        AS "Failed Backups Count",
    count(DISTINCT failed_backups)                               AS "Failed Backups Distinct"
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
-- part 7 of 18:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(last_value(failed_backups_trend ORDER BY time), 1)     AS "Failed Backups Trend",
    count(failed_backups_trend)                                  AS "Failed Backups Trend Count",
    count(DISTINCT failed_backups_trend)                         AS "Failed Backups Trend Distinct",
    round(last_value(warn_temperature ORDER BY time), 1)         AS "Warn Temperature",
    count(warn_temperature)                                      AS "Warn Temperature Count",
    count(DISTINCT warn_temperature)                             AS "Warn Temperature Distinct"
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
-- part 8 of 18:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(last_value(warn_temperature_trend ORDER BY time), 1)   AS "Warn Temperature Trend",
    count(warn_temperature_trend)                                AS "Warn Temperature Trend Count",
    count(DISTINCT warn_temperature_trend)                       AS "Warn Temperature Trend Distinct",
    round(last_value(spin_fan_speed ORDER BY time), 1)           AS "Spin Fan Speed",
    count(spin_fan_speed)                                        AS "Spin Fan Speed Count",
    count(DISTINCT spin_fan_speed)                               AS "Spin Fan Speed Distinct"
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
-- part 9 of 18:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(last_value(spin_fan_speed_trend ORDER BY time), 1)     AS "Spin Fan Speed Trend",
    count(spin_fan_speed_trend)                                  AS "Spin Fan Speed Trend Count",
    count(DISTINCT spin_fan_speed_trend)                         AS "Spin Fan Speed Trend Distinct",
    round(last_value(life_used_drives ORDER BY time), 1)         AS "Life Used Drives",
    count(life_used_drives)                                      AS "Life Used Drives Count",
    count(DISTINCT life_used_drives)                             AS "Life Used Drives Distinct"
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
-- part 10 of 18:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(last_value(life_used_drives_trend ORDER BY time), 1)   AS "Life Used Drives Trend",
    count(life_used_drives_trend)                                AS "Life Used Drives Trend Count",
    count(DISTINCT life_used_drives_trend)                       AS "Life Used Drives Trend Distinct",
    round(last_value(used_home_space ORDER BY time), 1)          AS "Used Home Space",
    count(used_home_space)                                       AS "Used Home Space Count",
    count(DISTINCT used_home_space)                              AS "Used Home Space Distinct"
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
-- part 11 of 18:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(last_value(used_home_space_trend ORDER BY time), 1)    AS "Used Home Space Trend",
    count(used_home_space_trend)                                 AS "Used Home Space Trend Count",
    count(DISTINCT used_home_space_trend)                        AS "Used Home Space Trend Distinct",
    round(last_value(used_share_space ORDER BY time), 1)         AS "Used Share Space",
    count(used_share_space)                                      AS "Used Share Space Count",
    count(DISTINCT used_share_space)                             AS "Used Share Space Distinct"
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
-- part 12 of 18:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(last_value(used_share_space_trend ORDER BY time), 1)   AS "Used Share Space Trend",
    count(used_share_space_trend)                                AS "Used Share Space Trend Count",
    count(DISTINCT used_share_space_trend)                       AS "Used Share Space Trend Distinct",
    round(last_value(used_backup_space ORDER BY time), 1)        AS "Used Backup Space",
    count(used_backup_space)                                     AS "Used Backup Space Count",
    count(DISTINCT used_backup_space)                            AS "Used Backup Space Distinct"
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
-- part 13 of 18:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(last_value(used_backup_space_trend ORDER BY time), 1)  AS "Used Backup Space Trend",
    count(used_backup_space_trend)                               AS "Used Backup Space Trend Count",
    count(DISTINCT used_backup_space_trend)                      AS "Used Backup Space Trend Distinct",
    round(last_value(used_swap_space ORDER BY time), 1)          AS "Used Swap Space",
    count(used_swap_space)                                       AS "Used Swap Space Count",
    count(DISTINCT used_swap_space)                              AS "Used Swap Space Distinct"
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
-- part 14 of 18:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(last_value(used_swap_space_trend ORDER BY time), 1)    AS "Used Swap Space Trend",
    count(used_swap_space_trend)                                 AS "Used Swap Space Trend Count",
    count(DISTINCT used_swap_space_trend)                        AS "Used Swap Space Trend Distinct",
    round(last_value(used_disk_ops ORDER BY time), 1)            AS "Used Disk Ops",
    count(used_disk_ops)                                         AS "Used Disk Ops Count",
    count(DISTINCT used_disk_ops)                                AS "Used Disk Ops Distinct"
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
-- part 15 of 18:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(last_value(used_disk_ops_trend ORDER BY time), 1)      AS "Used Disk Ops Trend",
    count(used_disk_ops_trend)                                   AS "Used Disk Ops Trend Count",
    count(DISTINCT used_disk_ops_trend)                          AS "Used Disk Ops Trend Distinct",
    round(last_value(used_network ORDER BY time), 1)             AS "Used Network",
    count(used_network)                                          AS "Used Network Count",
    count(DISTINCT used_network)                                 AS "Used Network Distinct"
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
-- part 16 of 18:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(last_value(used_network_trend ORDER BY time), 1)       AS "Used Network Trend",
    count(used_network_trend)                                    AS "Used Network Trend Count",
    count(DISTINCT used_network_trend)                           AS "Used Network Trend Distinct",
    round(avg(temperature), 1)                                   AS "Temperature Avg",
    round(min(temperature), 1)                                   AS "Temperature Min",
    round(max(temperature), 1)                                   AS "Temperature Max",
    count(temperature)                                           AS "Temperature Count",
    count(DISTINCT temperature)                                  AS "Temperature Distinct"
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
-- part 17 of 18:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(avg(temperature_trend), 1)                             AS "Temperature Trend Avg",
    round(min(temperature_trend), 1)                             AS "Temperature Trend Min",
    round(max(temperature_trend), 1)                             AS "Temperature Trend Max",
    count(temperature_trend)                                     AS "Temperature Trend Count",
    count(DISTINCT temperature_trend)                            AS "Temperature Trend Distinct",
    round(last_value(failed_drives ORDER BY time), 1)            AS "Failed Drives",
    count(failed_drives)                                         AS "Failed Drives Count",
    count(DISTINCT failed_drives)                                AS "Failed Drives Distinct"
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
-- part 18 of 18:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(last_value(failed_drives_trend ORDER BY time), 1)      AS "Failed Drives Trend",
    count(failed_drives_trend)                                   AS "Failed Drives Trend Count",
    count(DISTINCT failed_drives_trend)                          AS "Failed Drives Trend Distinct"
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
-- part 1 of 10:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    service                                                      AS "Service",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(avg(status), 1)                                        AS "Status Fraction",
    count(status)                                                AS "Status Count",
    count(DISTINCT status)                                       AS "Status Distinct",
    round(avg(status_trend), 1)                                  AS "Status Trend Fraction",
    count(status_trend)                                          AS "Status Trend Count",
    count(DISTINCT status_trend)                                 AS "Status Trend Distinct"
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
-- part 2 of 10:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    service                                                      AS "Service",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(avg(backup_status), 1)                                 AS "Backup Status Fraction",
    count(backup_status)                                         AS "Backup Status Count",
    count(DISTINCT backup_status)                                AS "Backup Status Distinct",
    round(avg(backup_status_trend), 1)                           AS "Backup Status Trend Fraction",
    count(backup_status_trend)                                   AS "Backup Status Trend Count",
    count(DISTINCT backup_status_trend)                          AS "Backup Status Trend Distinct"
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
-- part 3 of 10:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    service                                                      AS "Service",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(avg(health_status), 1)                                 AS "Health Status Fraction",
    count(health_status)                                         AS "Health Status Count",
    count(DISTINCT health_status)                                AS "Health Status Distinct",
    round(avg(health_status_trend), 1)                           AS "Health Status Trend Fraction",
    count(health_status_trend)                                   AS "Health Status Trend Count",
    count(DISTINCT health_status_trend)                          AS "Health Status Trend Distinct"
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
-- part 4 of 10:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    service                                                      AS "Service",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(avg(configured_status), 1)                             AS "Configured Status Fraction",
    count(configured_status)                                     AS "Configured Status Count",
    count(DISTINCT configured_status)                            AS "Configured Status Distinct",
    round(avg(configured_status_trend), 1)                       AS "Configured Status Trend Fraction",
    count(configured_status_trend)                               AS "Configured Status Trend Count",
    count(DISTINCT configured_status_trend)                      AS "Configured Status Trend Distinct"
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
-- part 5 of 10:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    service                                                      AS "Service",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(last_value(used_processor ORDER BY time), 1)           AS "Used Processor",
    count(used_processor)                                        AS "Used Processor Count",
    count(DISTINCT used_processor)                               AS "Used Processor Distinct",
    round(last_value(used_processor_trend ORDER BY time), 1)     AS "Used Processor Trend",
    count(used_processor_trend)                                  AS "Used Processor Trend Count",
    count(DISTINCT used_processor_trend)                         AS "Used Processor Trend Distinct"
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
-- part 6 of 10:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    service                                                      AS "Service",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(last_value(used_memory ORDER BY time), 1)              AS "Used Memory",
    count(used_memory)                                           AS "Used Memory Count",
    count(DISTINCT used_memory)                                  AS "Used Memory Distinct",
    round(last_value(used_memory_trend ORDER BY time), 1)        AS "Used Memory Trend",
    count(used_memory_trend)                                     AS "Used Memory Trend Count",
    count(DISTINCT used_memory_trend)                            AS "Used Memory Trend Distinct"
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
-- part 7 of 10:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    service                                                      AS "Service",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(last_value(used_disk_ops ORDER BY time), 1)            AS "Used Disk Ops",
    count(used_disk_ops)                                         AS "Used Disk Ops Count",
    count(DISTINCT used_disk_ops)                                AS "Used Disk Ops Distinct",
    round(last_value(used_disk_ops_trend ORDER BY time), 1)      AS "Used Disk Ops Trend",
    count(used_disk_ops_trend)                                   AS "Used Disk Ops Trend Count",
    count(DISTINCT used_disk_ops_trend)                          AS "Used Disk Ops Trend Distinct"
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
-- part 8 of 10:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    service                                                      AS "Service",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(last_value(used_network ORDER BY time), 1)             AS "Used Network",
    count(used_network)                                          AS "Used Network Count",
    count(DISTINCT used_network)                                 AS "Used Network Distinct",
    round(last_value(used_network_trend ORDER BY time), 1)       AS "Used Network Trend",
    count(used_network_trend)                                    AS "Used Network Trend Count",
    count(DISTINCT used_network_trend)                           AS "Used Network Trend Distinct"
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
-- part 9 of 10:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    service                                                      AS "Service",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(avg(restart_count), 1)                                 AS "Restart Count Avg",
    round(min(restart_count), 1)                                 AS "Restart Count Min",
    round(max(restart_count), 1)                                 AS "Restart Count Max",
    count(restart_count)                                         AS "Restart Count Count",
    count(DISTINCT restart_count)                                AS "Restart Count Distinct"
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
-- part 10 of 10:
SELECT
    date_bin(INTERVAL '15 minute', time + INTERVAL '480 minute') AS "Bucket",
    host                                                         AS "Host",
    service                                                      AS "Service",
    count(*)                                                     AS "Rows",
    min(time) + INTERVAL '480 minute'                            AS "Oldest",
    max(time) + INTERVAL '480 minute'                            AS "Newest",
    round(avg(restart_count_trend), 1)                           AS "Restart Count Trend Avg",
    round(min(restart_count_trend), 1)                           AS "Restart Count Trend Min",
    round(max(restart_count_trend), 1)                           AS "Restart Count Trend Max",
    count(restart_count_trend)                                   AS "Restart Count Trend Count",
    count(DISTINCT restart_count_trend)                          AS "Restart Count Trend Distinct"
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NOT NULL
    AND time >= now() - INTERVAL '1500 minute'
    AND time >= (SELECT max(time) FROM supervisor) - INTERVAL '15 minute'
GROUP BY "Bucket", host, service
ORDER BY "Bucket", host, service;
