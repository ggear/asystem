--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- diagnosis/plugin [health and diagnosis score of one network plugin] every 15m, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    plugin                                                   AS "Plugin",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(ok), 1)                                        AS "Ok Fraction",
    count(ok)                                                AS "Ok Count",
    count(DISTINCT ok)                                       AS "Ok Distinct",
    round(last_value(score ORDER BY time), 1)                AS "Score",
    count(score)                                             AS "Score Count",
    count(DISTINCT score)                                    AS "Score Distinct"
FROM diagnosis
WHERE
    module = 'network'
    AND plugin IS NOT NULL
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM diagnosis) - INTERVAL '1 day'
GROUP BY "Bucket", plugin
ORDER BY "Bucket", plugin;
