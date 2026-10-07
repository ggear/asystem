--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- wireless/accesspoint [access point health, one row per access point] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 5:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    accesspoint                                              AS "Accesspoint",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(up), 1)                                        AS "Up Fraction",
    count(up)                                                AS "Up Count",
    count(DISTINCT up)                                       AS "Up Distinct",
    round(avg(restarted), 1)                                 AS "Restarted Fraction",
    count(restarted)                                         AS "Restarted Count",
    count(DISTINCT restarted)                                AS "Restarted Distinct",
    round(avg(overheating), 1)                               AS "Overheating Fraction",
    count(overheating)                                       AS "Overheating Count",
    count(DISTINCT overheating)                              AS "Overheating Distinct"
FROM wireless
WHERE
    module = 'network'
    AND accesspoint IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM wireless) - INTERVAL '1 day'
GROUP BY "Bucket", accesspoint
ORDER BY "Bucket", accesspoint;

-- wireless/accesspoint [access point health, one row per access point] every 15m, bucketed [1 day] across the newest two buckets
-- part 2 of 5:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    accesspoint                                              AS "Accesspoint",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(experience_pct), 1)                            AS "Experience Pct Avg",
    round(min(experience_pct), 1)                            AS "Experience Pct Min",
    round(max(experience_pct), 1)                            AS "Experience Pct Max",
    count(experience_pct)                                    AS "Experience Pct Count",
    count(DISTINCT experience_pct)                           AS "Experience Pct Distinct"
FROM wireless
WHERE
    module = 'network'
    AND accesspoint IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM wireless) - INTERVAL '1 day'
GROUP BY "Bucket", accesspoint
ORDER BY "Bucket", accesspoint;

-- wireless/accesspoint [access point health, one row per access point] every 15m, bucketed [1 day] across the newest two buckets
-- part 3 of 5:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    accesspoint                                              AS "Accesspoint",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(throughput_mbps), 1)                           AS "Throughput Mbps Avg",
    round(min(throughput_mbps), 1)                           AS "Throughput Mbps Min",
    round(max(throughput_mbps), 1)                           AS "Throughput Mbps Max",
    count(throughput_mbps)                                   AS "Throughput Mbps Count",
    count(DISTINCT throughput_mbps)                          AS "Throughput Mbps Distinct"
FROM wireless
WHERE
    module = 'network'
    AND accesspoint IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM wireless) - INTERVAL '1 day'
GROUP BY "Bucket", accesspoint
ORDER BY "Bucket", accesspoint;

-- wireless/accesspoint [access point health, one row per access point] every 15m, bucketed [1 day] across the newest two buckets
-- part 4 of 5:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    accesspoint                                              AS "Accesspoint",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(network_pct), 1)                               AS "Network Pct Avg",
    round(min(network_pct), 1)                               AS "Network Pct Min",
    round(max(network_pct), 1)                               AS "Network Pct Max",
    count(network_pct)                                       AS "Network Pct Count",
    count(DISTINCT network_pct)                              AS "Network Pct Distinct",
    round(last_value(clients ORDER BY time), 1)              AS "Clients",
    count(clients)                                           AS "Clients Count",
    count(DISTINCT clients)                                  AS "Clients Distinct"
FROM wireless
WHERE
    module = 'network'
    AND accesspoint IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM wireless) - INTERVAL '1 day'
GROUP BY "Bucket", accesspoint
ORDER BY "Bucket", accesspoint;

-- wireless/accesspoint [access point health, one row per access point] every 15m, bucketed [1 day] across the newest two buckets
-- part 5 of 5:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    accesspoint                                              AS "Accesspoint",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(cpu_pct), 1)                                   AS "Cpu Pct Avg",
    round(min(cpu_pct), 1)                                   AS "Cpu Pct Min",
    round(max(cpu_pct), 1)                                   AS "Cpu Pct Max",
    count(cpu_pct)                                           AS "Cpu Pct Count",
    count(DISTINCT cpu_pct)                                  AS "Cpu Pct Distinct",
    round(avg(memory_pct), 1)                                AS "Memory Pct Avg",
    round(min(memory_pct), 1)                                AS "Memory Pct Min",
    round(max(memory_pct), 1)                                AS "Memory Pct Max",
    count(memory_pct)                                        AS "Memory Pct Count",
    count(DISTINCT memory_pct)                               AS "Memory Pct Distinct"
FROM wireless
WHERE
    module = 'network'
    AND accesspoint IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM wireless) - INTERVAL '1 day'
GROUP BY "Bucket", accesspoint
ORDER BY "Bucket", accesspoint;
