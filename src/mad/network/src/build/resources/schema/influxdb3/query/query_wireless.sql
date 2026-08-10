--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- wireless/accesspoint [access point health, one row per access point] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time)            AS "Bucket",
    accesspoint                                 AS "Accesspoint",
    round(avg(up), 1)                           AS "Up Fraction",
    round(avg(experience_pct), 1)               AS "Experience Pct Avg",
    round(min(experience_pct), 1)               AS "Experience Pct Min",
    round(max(experience_pct), 1)               AS "Experience Pct Max",
    round(last_value(clients ORDER BY time), 1) AS "Clients"
FROM wireless
WHERE
    accesspoint IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM wireless) - INTERVAL '1 day'
GROUP BY "Bucket", accesspoint
ORDER BY "Bucket", accesspoint;
