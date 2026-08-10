--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- certificate/endpoint [certificate health, one row per monitored endpoint] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    endpoint                         AS "Endpoint",
    round(avg(verified), 1)          AS "Verified Fraction",
    round(avg(expiry_days), 1)       AS "Expiry Days Avg",
    round(min(expiry_days), 1)       AS "Expiry Days Min",
    round(max(expiry_days), 1)       AS "Expiry Days Max",
    round(avg(validity_pct), 1)      AS "Validity Pct Avg",
    round(min(validity_pct), 1)      AS "Validity Pct Min",
    round(max(validity_pct), 1)      AS "Validity Pct Max"
FROM certificate
WHERE
    endpoint IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM certificate) - INTERVAL '1 day'
GROUP BY "Bucket", endpoint
ORDER BY "Bucket", endpoint;
