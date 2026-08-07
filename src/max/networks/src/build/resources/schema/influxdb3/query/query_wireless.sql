--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- wireless/accesspoint [access point health across the wireless estate] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time)              AS "Bucket",
    round(avg(ok), 1)                             AS "Ok Fraction",
    round(last_value(score ORDER BY time), 1)     AS "Score",
    round(last_value(aps_total ORDER BY time), 1) AS "Aps Total",
    round(last_value(aps_ok ORDER BY time), 1)    AS "Aps Ok",
    round(avg(avg_experience_pct), 1)             AS "Avg Experience Pct Avg",
    round(min(avg_experience_pct), 1)             AS "Avg Experience Pct Min",
    round(max(avg_experience_pct), 1)             AS "Avg Experience Pct Max"
FROM wireless
WHERE
    time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM wireless) - INTERVAL '1 day'
GROUP BY "Bucket"
ORDER BY "Bucket";
