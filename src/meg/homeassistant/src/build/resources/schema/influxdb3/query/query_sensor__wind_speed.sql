--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- sensor__wind_speed [Home Assistant sensor__wind_speed] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 3:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    unit_of_measurement              AS "Unit Of Measurement",
    round(avg(bom_id), 1)            AS "Bom Id Avg",
    round(min(bom_id), 1)            AS "Bom Id Min",
    round(max(bom_id), 1)            AS "Bom Id Max",
    round(avg(distance), 1)          AS "Distance Avg",
    round(min(distance), 1)          AS "Distance Min",
    round(max(distance), 1)          AS "Distance Max",
    round(avg(issue_time), 1)        AS "Issue Time Avg",
    round(min(issue_time), 1)        AS "Issue Time Min",
    round(max(issue_time), 1)        AS "Issue Time Max"
FROM sensor__wind_speed
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor__wind_speed) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor__wind_speed [Home Assistant sensor__wind_speed] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 2 of 3:
SELECT
    date_bin(INTERVAL '1 day', time)  AS "Bucket",
    entity_id                         AS "Entity Id",
    unit_of_measurement               AS "Unit Of Measurement",
    round(avg(observation_time), 1)   AS "Observation Time Avg",
    round(min(observation_time), 1)   AS "Observation Time Min",
    round(max(observation_time), 1)   AS "Observation Time Max",
    round(avg(response_timestamp), 1) AS "Response Timestamp Avg",
    round(min(response_timestamp), 1) AS "Response Timestamp Min"
FROM sensor__wind_speed
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor__wind_speed) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor__wind_speed [Home Assistant sensor__wind_speed] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 3 of 3:
SELECT
    date_bin(INTERVAL '1 day', time)  AS "Bucket",
    entity_id                         AS "Entity Id",
    unit_of_measurement               AS "Unit Of Measurement",
    round(max(response_timestamp), 1) AS "Response Timestamp Max",
    round(avg(value), 1)              AS "Value Avg",
    round(min(value), 1)              AS "Value Min",
    round(max(value), 1)              AS "Value Max"
FROM sensor__wind_speed
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor__wind_speed) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;
