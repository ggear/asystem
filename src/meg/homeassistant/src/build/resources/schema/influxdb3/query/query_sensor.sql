--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 7:
SELECT
    date_bin(INTERVAL '1 day', time)     AS "Bucket",
    entity_id                            AS "Entity Id",
    unit_of_measurement                  AS "Unit Of Measurement",
    round(avg(Available), 1)             AS "Available Avg",
    round(min(Available), 1)             AS "Available Min",
    round(max(Available), 1)             AS "Available Max",
    round(avg(Available (Important)), 1) AS "Available (important) Avg",
    round(min(Available (Important)), 1) AS "Available (important) Min",
    round(max(Available (Important)), 1) AS "Available (important) Max"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 2 of 7:
SELECT
    date_bin(INTERVAL '1 day', time)         AS "Bucket",
    entity_id                                AS "Entity Id",
    unit_of_measurement                      AS "Unit Of Measurement",
    round(avg(Available (Opportunistic)), 1) AS "Available (opportunistic) Avg",
    round(min(Available (Opportunistic)), 1) AS "Available (opportunistic) Min",
    round(max(Available (Opportunistic)), 1) AS "Available (opportunistic) Max",
    round(avg(Low Power Mode), 1)            AS "Low power mode Avg",
    round(min(Low Power Mode), 1)            AS "Low power mode Min"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 3 of 7:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    unit_of_measurement              AS "Unit Of Measurement",
    round(max(Low Power Mode), 1)    AS "Low power mode Max",
    round(avg(Name), 1)              AS "Name Avg",
    round(min(Name), 1)              AS "Name Min",
    round(max(Name), 1)              AS "Name Max",
    round(avg(Postal Code), 1)       AS "Postal code Avg",
    round(min(Postal Code), 1)       AS "Postal code Min",
    round(max(Postal Code), 1)       AS "Postal code Max",
    round(avg(Sub Thoroughfare), 1)  AS "Sub thoroughfare Avg"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 4 of 7:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    unit_of_measurement              AS "Unit Of Measurement",
    round(min(Sub Thoroughfare), 1)  AS "Sub thoroughfare Min",
    round(max(Sub Thoroughfare), 1)  AS "Sub thoroughfare Max",
    round(avg(Total), 1)             AS "Total Avg",
    round(min(Total), 1)             AS "Total Min",
    round(max(Total), 1)             AS "Total Max",
    round(avg(bom_id), 1)            AS "Bom Id Avg",
    round(min(bom_id), 1)            AS "Bom Id Min",
    round(max(bom_id), 1)            AS "Bom Id Max",
    round(avg(date), 1)              AS "Date Avg"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 5 of 7:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    unit_of_measurement              AS "Unit Of Measurement",
    round(min(date), 1)              AS "Date Min",
    round(max(date), 1)              AS "Date Max",
    round(avg(distance), 1)          AS "Distance Avg",
    round(min(distance), 1)          AS "Distance Min",
    round(max(distance), 1)          AS "Distance Max",
    round(avg(issue_time), 1)        AS "Issue Time Avg",
    round(min(issue_time), 1)        AS "Issue Time Min",
    round(max(issue_time), 1)        AS "Issue Time Max",
    round(avg(next_issue_time), 1)   AS "Next Issue Time Avg"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 6 of 7:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    unit_of_measurement              AS "Unit Of Measurement",
    round(min(next_issue_time), 1)   AS "Next Issue Time Min",
    round(max(next_issue_time), 1)   AS "Next Issue Time Max",
    round(avg(next_reset), 1)        AS "Next Reset Avg",
    round(min(next_reset), 1)        AS "Next Reset Min",
    round(max(next_reset), 1)        AS "Next Reset Max",
    round(avg(observation_time), 1)  AS "Observation Time Avg",
    round(min(observation_time), 1)  AS "Observation Time Min"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 7 of 7:
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
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;
