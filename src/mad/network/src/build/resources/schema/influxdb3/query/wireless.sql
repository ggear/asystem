--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- wireless/accesspoint [access point health, one row per access point] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    accesspoint                                              AS "Accesspoint",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(up), 1)                                        AS "Up Fraction",
    count(up)                                                AS "Up Count",
    count(DISTINCT up)                                       AS "Up Distinct",
    round(avg(experience_pct), 1)                            AS "Experience Pct Avg",
    round(min(experience_pct), 1)                            AS "Experience Pct Min",
    round(max(experience_pct), 1)                            AS "Experience Pct Max",
    count(experience_pct)                                    AS "Experience Pct Count",
    count(DISTINCT experience_pct)                           AS "Experience Pct Distinct",
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
