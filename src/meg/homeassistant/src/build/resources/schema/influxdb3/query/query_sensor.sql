--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 5:
SELECT
    date_bin(INTERVAL '1 day', time)                                                               AS "Bucket",
    entity_id                                                                                      AS "Entity Id",
    unit_of_measurement                                                                            AS "Unit Of Measurement",
    round(avg("Active Alarm (BAYSWATER, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 810058)"), 1) AS "Active alarm (bayswater, city of bayswater, metro north east, cad-id: 810058)",
    round(avg("Active Alarm (EMBLETON, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 810033)"), 1)  AS "Active alarm (embleton, city of bayswater, metro north east, cad-id: 810033)",
    round(avg("Active Alarm (GUILDFORD, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809971)"), 1)      AS "Active alarm (guildford, city of swan, metro north east, cad-id: 809971)"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 2 of 5:
SELECT
    date_bin(INTERVAL '1 day', time)                                                     AS "Bucket",
    entity_id                                                                            AS "Entity Id",
    unit_of_measurement                                                                  AS "Unit Of Measurement",
    round(avg("Available"), 1)                                                           AS "Available",
    round(avg("Available (Important)"), 1)                                               AS "Available (important)",
    round(avg("Available (Opportunistic)"), 1)                                           AS "Available (opportunistic)",
    round(avg("Burn Off (LEXIA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809996)"), 1)    AS "Burn off (lexia, city of swan, metro north east, cad-id: 809996)",
    round(avg("Burn Off (WHITEMAN, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810037)"), 1) AS "Burn off (whiteman, city of swan, metro north east, cad-id: 810037)"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 3 of 5:
SELECT
    date_bin(INTERVAL '1 day', time)                                                           AS "Bucket",
    entity_id                                                                                  AS "Entity Id",
    unit_of_measurement                                                                        AS "Unit Of Measurement",
    round(avg("Burn Off (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810023)"), 1) AS "Burn off (wooroloo, shire of mundaring, metro north east, cad-id: 810023)",
    round(avg("Bushfire (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810022)"), 1) AS "Bushfire (wooroloo, shire of mundaring, metro north east, cad-id: 810022)",
    round(avg("Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)"), 1)       AS "Fire (henley brook, city of swan, metro north east, cad-id: 809994)",
    round(avg("Low Power Mode"), 1)                                                            AS "Low power mode"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 4 of 5:
SELECT
    date_bin(INTERVAL '1 day', time)                                                          AS "Bucket",
    entity_id                                                                                 AS "Entity Id",
    unit_of_measurement                                                                       AS "Unit Of Measurement",
    round(avg("Name"), 1)                                                                     AS "Name",
    round(avg("Postal Code"), 1)                                                              AS "Postal code",
    round(avg("Road Crash (BALLAJURA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810011)"), 1)   AS "Road crash (ballajura, city of swan, metro north east, cad-id: 810011)",
    round(avg("Road Crash (MORLEY, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 809968)"), 1) AS "Road crash (morley, city of bayswater, metro north east, cad-id: 809968)"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 5 of 5:
SELECT
    date_bin(INTERVAL '1 day', time)                                                               AS "Bucket",
    entity_id                                                                                      AS "Entity Id",
    unit_of_measurement                                                                            AS "Unit Of Measurement",
    round(avg("Structure Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)"), 1) AS "Structure fire (henley brook, city of swan, metro north east, cad-id: 809994)",
    round(avg("Sub Thoroughfare"), 1)                                                              AS "Sub thoroughfare",
    round(avg("Total"), 1)                                                                         AS "Total",
    round(avg(bom_id), 1)                                                                          AS "Bom Id",
    round(avg(date), 1)                                                                            AS "Date",
    round(avg(distance), 1)                                                                        AS "Distance",
    round(avg(issue_time), 1)                                                                      AS "Issue Time",
    round(avg(next_issue_time), 1)                                                                 AS "Next Issue Time",
    round(avg(next_reset), 1)                                                                      AS "Next Reset",
    round(avg(observation_time), 1)                                                                AS "Observation Time",
    round(avg(response_timestamp), 1)                                                              AS "Response Timestamp",
    round(avg(value), 1)                                                                           AS "Value"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;
