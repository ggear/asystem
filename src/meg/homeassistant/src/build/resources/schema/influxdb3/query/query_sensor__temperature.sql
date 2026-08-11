--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- sensor__temperature [Home Assistant sensor__temperature] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time)  AS "Bucket",
    entity_id                         AS "Entity Id",
    unit_of_measurement               AS "Unit Of Measurement",
    round(avg(bom_id), 1)             AS "Bom Id",
    round(avg(date), 1)               AS "Date",
    round(avg(distance), 1)           AS "Distance",
    round(avg(issue_time), 1)         AS "Issue Time",
    round(avg(latitude), 1)           AS "Latitude",
    round(avg(longitude), 1)          AS "Longitude",
    round(avg(next_issue_time), 1)    AS "Next Issue Time",
    round(avg(observation_time), 1)   AS "Observation Time",
    round(avg(response_timestamp), 1) AS "Response Timestamp",
    round(avg(time_observed), 1)      AS "Time Observed",
    round(avg(value), 1)              AS "Value"
FROM sensor__temperature
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor__temperature) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;
