--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- certificate/endpoint [certificate health, one row per monitored endpoint] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 2:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    endpoint                                                 AS "Endpoint",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(verified), 1)                                  AS "Verified Fraction",
    count(verified)                                          AS "Verified Count",
    count(DISTINCT verified)                                 AS "Verified Distinct",
    round(avg(expiry_days), 1)                               AS "Expiry Days Avg",
    round(min(expiry_days), 1)                               AS "Expiry Days Min",
    round(max(expiry_days), 1)                               AS "Expiry Days Max",
    count(expiry_days)                                       AS "Expiry Days Count",
    count(DISTINCT expiry_days)                              AS "Expiry Days Distinct"
FROM certificate
WHERE
    module = 'network'
    AND endpoint IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM certificate) - INTERVAL '1 day'
GROUP BY "Bucket", endpoint
ORDER BY "Bucket", endpoint;

-- certificate/endpoint [certificate health, one row per monitored endpoint] every 15m, bucketed [1 day] across the newest two buckets
-- part 2 of 2:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    endpoint                                                 AS "Endpoint",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(validity_pct), 1)                              AS "Validity Pct Avg",
    round(min(validity_pct), 1)                              AS "Validity Pct Min",
    round(max(validity_pct), 1)                              AS "Validity Pct Max",
    count(validity_pct)                                      AS "Validity Pct Count",
    count(DISTINCT validity_pct)                             AS "Validity Pct Distinct"
FROM certificate
WHERE
    module = 'network'
    AND endpoint IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM certificate) - INTERVAL '1 day'
GROUP BY "Bucket", endpoint
ORDER BY "Bucket", endpoint;
