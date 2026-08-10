--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- sensor__humidity [Home Assistant sensor__humidity] every <on-change>, bucketed [1 day] across the newest two buckets
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
FROM sensor__humidity
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor__humidity) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor__humidity [Home Assistant sensor__humidity] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 2 of 3:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    unit_of_measurement              AS "Unit Of Measurement",
    round(avg(latitude), 1)          AS "Latitude Avg",
    round(min(latitude), 1)          AS "Latitude Min",
    round(max(latitude), 1)          AS "Latitude Max",
    round(avg(longitude), 1)         AS "Longitude Avg",
    round(min(longitude), 1)         AS "Longitude Min",
    round(max(longitude), 1)         AS "Longitude Max",
    round(avg(observation_time), 1)  AS "Observation Time Avg",
    round(min(observation_time), 1)  AS "Observation Time Min"
FROM sensor__humidity
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor__humidity) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor__humidity [Home Assistant sensor__humidity] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 3 of 3:
SELECT
    date_bin(INTERVAL '1 day', time)  AS "Bucket",
    entity_id                         AS "Entity Id",
    unit_of_measurement               AS "Unit Of Measurement",
    round(max(observation_time), 1)   AS "Observation Time Max",
    round(avg(response_timestamp), 1) AS "Response Timestamp Avg",
    round(min(response_timestamp), 1) AS "Response Timestamp Min",
    round(max(response_timestamp), 1) AS "Response Timestamp Max",
    round(avg(value), 1)              AS "Value Avg",
    round(min(value), 1)              AS "Value Min",
    round(max(value), 1)              AS "Value Max"
FROM sensor__humidity
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor__humidity) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;
