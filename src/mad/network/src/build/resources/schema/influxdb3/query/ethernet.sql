--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- ethernet/powered [power drawn over ethernet, one row per device a monitored switch powers] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    powered                                                  AS "Powered",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(power_w), 1)                                   AS "Power W Avg",
    round(min(power_w), 1)                                   AS "Power W Min",
    round(max(power_w), 1)                                   AS "Power W Max",
    count(power_w)                                           AS "Power W Count",
    count(DISTINCT power_w)                                  AS "Power W Distinct"
FROM ethernet
WHERE
    module = 'network'
    AND powered IS NOT NULL
    AND switch IS NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM ethernet) - INTERVAL '1 day'
GROUP BY "Bucket", powered
ORDER BY "Bucket", powered;

-- ethernet/switch [wired network health, one row per gateway or switch] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 7:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    switch                                                   AS "Switch",
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
FROM ethernet
WHERE
    module = 'network'
    AND switch IS NOT NULL
    AND powered IS NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM ethernet) - INTERVAL '1 day'
GROUP BY "Bucket", switch
ORDER BY "Bucket", switch;

-- ethernet/switch [wired network health, one row per gateway or switch] every 15m, bucketed [1 day] across the newest two buckets
-- part 2 of 7:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    switch                                                   AS "Switch",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(experience_pct), 1)                            AS "Experience Pct Avg",
    round(min(experience_pct), 1)                            AS "Experience Pct Min",
    round(max(experience_pct), 1)                            AS "Experience Pct Max",
    count(experience_pct)                                    AS "Experience Pct Count",
    count(DISTINCT experience_pct)                           AS "Experience Pct Distinct"
FROM ethernet
WHERE
    module = 'network'
    AND switch IS NOT NULL
    AND powered IS NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM ethernet) - INTERVAL '1 day'
GROUP BY "Bucket", switch
ORDER BY "Bucket", switch;

-- ethernet/switch [wired network health, one row per gateway or switch] every 15m, bucketed [1 day] across the newest two buckets
-- part 3 of 7:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    switch                                                   AS "Switch",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(throughput_mbps), 1)                           AS "Throughput Mbps Avg",
    round(min(throughput_mbps), 1)                           AS "Throughput Mbps Min",
    round(max(throughput_mbps), 1)                           AS "Throughput Mbps Max",
    count(throughput_mbps)                                   AS "Throughput Mbps Count",
    count(DISTINCT throughput_mbps)                          AS "Throughput Mbps Distinct"
FROM ethernet
WHERE
    module = 'network'
    AND switch IS NOT NULL
    AND powered IS NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM ethernet) - INTERVAL '1 day'
GROUP BY "Bucket", switch
ORDER BY "Bucket", switch;

-- ethernet/switch [wired network health, one row per gateway or switch] every 15m, bucketed [1 day] across the newest two buckets
-- part 4 of 7:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    switch                                                   AS "Switch",
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
FROM ethernet
WHERE
    module = 'network'
    AND switch IS NOT NULL
    AND powered IS NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM ethernet) - INTERVAL '1 day'
GROUP BY "Bucket", switch
ORDER BY "Bucket", switch;

-- ethernet/switch [wired network health, one row per gateway or switch] every 15m, bucketed [1 day] across the newest two buckets
-- part 5 of 7:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    switch                                                   AS "Switch",
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
FROM ethernet
WHERE
    module = 'network'
    AND switch IS NOT NULL
    AND powered IS NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM ethernet) - INTERVAL '1 day'
GROUP BY "Bucket", switch
ORDER BY "Bucket", switch;

-- ethernet/switch [wired network health, one row per gateway or switch] every 15m, bucketed [1 day] across the newest two buckets
-- part 6 of 7:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    switch                                                   AS "Switch",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(temperature), 1)                               AS "Temperature Avg",
    round(min(temperature), 1)                               AS "Temperature Min",
    round(max(temperature), 1)                               AS "Temperature Max",
    count(temperature)                                       AS "Temperature Count",
    count(DISTINCT temperature)                              AS "Temperature Distinct",
    round(avg(poe_w), 1)                                     AS "Poe W Avg",
    round(min(poe_w), 1)                                     AS "Poe W Min",
    round(max(poe_w), 1)                                     AS "Poe W Max",
    count(poe_w)                                             AS "Poe W Count",
    count(DISTINCT poe_w)                                    AS "Poe W Distinct"
FROM ethernet
WHERE
    module = 'network'
    AND switch IS NOT NULL
    AND powered IS NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM ethernet) - INTERVAL '1 day'
GROUP BY "Bucket", switch
ORDER BY "Bucket", switch;

-- ethernet/switch [wired network health, one row per gateway or switch] every 15m, bucketed [1 day] across the newest two buckets
-- part 7 of 7:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    switch                                                   AS "Switch",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(poe_pct), 1)                                   AS "Poe Pct Avg",
    round(min(poe_pct), 1)                                   AS "Poe Pct Min",
    round(max(poe_pct), 1)                                   AS "Poe Pct Max",
    count(poe_pct)                                           AS "Poe Pct Count",
    count(DISTINCT poe_pct)                                  AS "Poe Pct Distinct"
FROM ethernet
WHERE
    module = 'network'
    AND switch IS NOT NULL
    AND powered IS NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM ethernet) - INTERVAL '1 day'
GROUP BY "Bucket", switch
ORDER BY "Bucket", switch;
