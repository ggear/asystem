--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- zigbee/device [mesh device state reported by the coordinator, one row per paired device] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    device                                                   AS "Device",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(available), 1)                                 AS "Available Fraction",
    count(available)                                         AS "Available Count",
    count(DISTINCT available)                                AS "Available Distinct",
    round(last_value(lqi ORDER BY time), 1)                  AS "Lqi",
    count(lqi)                                               AS "Lqi Count",
    count(DISTINCT lqi)                                      AS "Lqi Distinct",
    round(avg(weak), 1)                                      AS "Weak Fraction",
    count(weak)                                              AS "Weak Count",
    count(DISTINCT weak)                                     AS "Weak Distinct",
    round(last_value(last_seen_s ORDER BY time), 1)          AS "Last Seen S",
    count(last_seen_s)                                       AS "Last Seen S Count",
    count(DISTINCT last_seen_s)                              AS "Last Seen S Distinct"
FROM zigbee
WHERE
    module = 'network'
    AND device IS NOT NULL
    AND experience IS NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM zigbee) - INTERVAL '1 day'
GROUP BY "Bucket", device
ORDER BY "Bucket", device;

-- zigbee/experience [mesh experience, one row per part of the mesh] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    experience                                               AS "Experience",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(experience_pct), 1)                            AS "Experience Pct Avg",
    round(min(experience_pct), 1)                            AS "Experience Pct Min",
    round(max(experience_pct), 1)                            AS "Experience Pct Max",
    count(experience_pct)                                    AS "Experience Pct Count",
    count(DISTINCT experience_pct)                           AS "Experience Pct Distinct"
FROM zigbee
WHERE
    module = 'network'
    AND experience IS NOT NULL
    AND device IS NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM zigbee) - INTERVAL '1 day'
GROUP BY "Bucket", experience
ORDER BY "Bucket", experience;
