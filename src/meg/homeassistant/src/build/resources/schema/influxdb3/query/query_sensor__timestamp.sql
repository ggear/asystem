--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- sensor__timestamp [Home Assistant sensor__timestamp] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 2:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(avg(date), 1)              AS "Date Avg",
    round(min(date), 1)              AS "Date Min",
    round(max(date), 1)              AS "Date Max",
    round(avg(issue_time), 1)        AS "Issue Time Avg",
    round(min(issue_time), 1)        AS "Issue Time Min",
    round(max(issue_time), 1)        AS "Issue Time Max",
    round(avg(next_issue_time), 1)   AS "Next Issue Time Avg",
    round(min(next_issue_time), 1)   AS "Next Issue Time Min",
    round(max(next_issue_time), 1)   AS "Next Issue Time Max"
FROM sensor__timestamp
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor__timestamp) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- sensor__timestamp [Home Assistant sensor__timestamp] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 2 of 2:
SELECT
    date_bin(INTERVAL '1 day', time)  AS "Bucket",
    entity_id                         AS "Entity Id",
    round(avg(response_timestamp), 1) AS "Response Timestamp Avg",
    round(min(response_timestamp), 1) AS "Response Timestamp Min",
    round(max(response_timestamp), 1) AS "Response Timestamp Max"
FROM sensor__timestamp
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor__timestamp) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
