--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                              AS "Bucket",
    entity_id                                                                                     AS "Entity Id",
    unit_of_measurement                                                                           AS "Unit Of Measurement",
    round(avg("Active Alarm (EMBLETON, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 810033)"), 1) AS "Active alarm (embleton, city of bayswater, metro north east, cad-id: 810033) Avg"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 2 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                              AS "Bucket",
    entity_id                                                                                     AS "Entity Id",
    unit_of_measurement                                                                           AS "Unit Of Measurement",
    round(min("Active Alarm (EMBLETON, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 810033)"), 1) AS "Active alarm (embleton, city of bayswater, metro north east, cad-id: 810033) Min"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 3 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                              AS "Bucket",
    entity_id                                                                                     AS "Entity Id",
    unit_of_measurement                                                                           AS "Unit Of Measurement",
    round(max("Active Alarm (EMBLETON, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 810033)"), 1) AS "Active alarm (embleton, city of bayswater, metro north east, cad-id: 810033) Max"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 4 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                          AS "Bucket",
    entity_id                                                                                 AS "Entity Id",
    unit_of_measurement                                                                       AS "Unit Of Measurement",
    round(avg("Active Alarm (GUILDFORD, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809971)"), 1) AS "Active alarm (guildford, city of swan, metro north east, cad-id: 809971) Avg"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 5 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                          AS "Bucket",
    entity_id                                                                                 AS "Entity Id",
    unit_of_measurement                                                                       AS "Unit Of Measurement",
    round(min("Active Alarm (GUILDFORD, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809971)"), 1) AS "Active alarm (guildford, city of swan, metro north east, cad-id: 809971) Min"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 6 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                          AS "Bucket",
    entity_id                                                                                 AS "Entity Id",
    unit_of_measurement                                                                       AS "Unit Of Measurement",
    round(max("Active Alarm (GUILDFORD, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809971)"), 1) AS "Active alarm (guildford, city of swan, metro north east, cad-id: 809971) Max",
    round(avg("Available"), 1)                                                                AS "Available Avg",
    round(min("Available"), 1)                                                                AS "Available Min",
    round(max("Available"), 1)                                                                AS "Available Max"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 7 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)           AS "Bucket",
    entity_id                                  AS "Entity Id",
    unit_of_measurement                        AS "Unit Of Measurement",
    round(avg("Available (Important)"), 1)     AS "Available (important) Avg",
    round(min("Available (Important)"), 1)     AS "Available (important) Min",
    round(max("Available (Important)"), 1)     AS "Available (important) Max",
    round(avg("Available (Opportunistic)"), 1) AS "Available (opportunistic) Avg"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 8 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                  AS "Bucket",
    entity_id                                                                         AS "Entity Id",
    unit_of_measurement                                                               AS "Unit Of Measurement",
    round(min("Available (Opportunistic)"), 1)                                        AS "Available (opportunistic) Min",
    round(max("Available (Opportunistic)"), 1)                                        AS "Available (opportunistic) Max",
    round(avg("Burn Off (LEXIA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809996)"), 1) AS "Burn off (lexia, city of swan, metro north east, cad-id: 809996) Avg"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 9 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                  AS "Bucket",
    entity_id                                                                         AS "Entity Id",
    unit_of_measurement                                                               AS "Unit Of Measurement",
    round(min("Burn Off (LEXIA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809996)"), 1) AS "Burn off (lexia, city of swan, metro north east, cad-id: 809996) Min"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 10 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                  AS "Bucket",
    entity_id                                                                         AS "Entity Id",
    unit_of_measurement                                                               AS "Unit Of Measurement",
    round(max("Burn Off (LEXIA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809996)"), 1) AS "Burn off (lexia, city of swan, metro north east, cad-id: 809996) Max"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 11 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                     AS "Bucket",
    entity_id                                                                            AS "Entity Id",
    unit_of_measurement                                                                  AS "Unit Of Measurement",
    round(avg("Burn Off (WHITEMAN, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810037)"), 1) AS "Burn off (whiteman, city of swan, metro north east, cad-id: 810037) Avg"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 12 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                     AS "Bucket",
    entity_id                                                                            AS "Entity Id",
    unit_of_measurement                                                                  AS "Unit Of Measurement",
    round(min("Burn Off (WHITEMAN, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810037)"), 1) AS "Burn off (whiteman, city of swan, metro north east, cad-id: 810037) Min"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 13 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                     AS "Bucket",
    entity_id                                                                            AS "Entity Id",
    unit_of_measurement                                                                  AS "Unit Of Measurement",
    round(max("Burn Off (WHITEMAN, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810037)"), 1) AS "Burn off (whiteman, city of swan, metro north east, cad-id: 810037) Max"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 14 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                           AS "Bucket",
    entity_id                                                                                  AS "Entity Id",
    unit_of_measurement                                                                        AS "Unit Of Measurement",
    round(avg("Burn Off (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810023)"), 1) AS "Burn off (wooroloo, shire of mundaring, metro north east, cad-id: 810023) Avg"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 15 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                           AS "Bucket",
    entity_id                                                                                  AS "Entity Id",
    unit_of_measurement                                                                        AS "Unit Of Measurement",
    round(min("Burn Off (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810023)"), 1) AS "Burn off (wooroloo, shire of mundaring, metro north east, cad-id: 810023) Min"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 16 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                           AS "Bucket",
    entity_id                                                                                  AS "Entity Id",
    unit_of_measurement                                                                        AS "Unit Of Measurement",
    round(max("Burn Off (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810023)"), 1) AS "Burn off (wooroloo, shire of mundaring, metro north east, cad-id: 810023) Max"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 17 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                           AS "Bucket",
    entity_id                                                                                  AS "Entity Id",
    unit_of_measurement                                                                        AS "Unit Of Measurement",
    round(avg("Bushfire (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810022)"), 1) AS "Bushfire (wooroloo, shire of mundaring, metro north east, cad-id: 810022) Avg"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 18 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                           AS "Bucket",
    entity_id                                                                                  AS "Entity Id",
    unit_of_measurement                                                                        AS "Unit Of Measurement",
    round(min("Bushfire (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810022)"), 1) AS "Bushfire (wooroloo, shire of mundaring, metro north east, cad-id: 810022) Min"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 19 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                           AS "Bucket",
    entity_id                                                                                  AS "Entity Id",
    unit_of_measurement                                                                        AS "Unit Of Measurement",
    round(max("Bushfire (WOOROLOO, SHIRE OF MUNDARING, METRO NORTH EAST, CAD-ID: 810022)"), 1) AS "Bushfire (wooroloo, shire of mundaring, metro north east, cad-id: 810022) Max"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 20 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                     AS "Bucket",
    entity_id                                                                            AS "Entity Id",
    unit_of_measurement                                                                  AS "Unit Of Measurement",
    round(avg("Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)"), 1) AS "Fire (henley brook, city of swan, metro north east, cad-id: 809994) Avg"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 21 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                     AS "Bucket",
    entity_id                                                                            AS "Entity Id",
    unit_of_measurement                                                                  AS "Unit Of Measurement",
    round(min("Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)"), 1) AS "Fire (henley brook, city of swan, metro north east, cad-id: 809994) Min"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 22 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                     AS "Bucket",
    entity_id                                                                            AS "Entity Id",
    unit_of_measurement                                                                  AS "Unit Of Measurement",
    round(max("Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)"), 1) AS "Fire (henley brook, city of swan, metro north east, cad-id: 809994) Max",
    round(avg("Low Power Mode"), 1)                                                      AS "Low power mode Avg",
    round(min("Low Power Mode"), 1)                                                      AS "Low power mode Min",
    round(max("Low Power Mode"), 1)                                                      AS "Low power mode Max"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 23 of 36:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    unit_of_measurement              AS "Unit Of Measurement",
    round(avg("Name"), 1)            AS "Name Avg",
    round(min("Name"), 1)            AS "Name Min",
    round(max("Name"), 1)            AS "Name Max",
    round(avg("Postal Code"), 1)     AS "Postal code Avg",
    round(min("Postal Code"), 1)     AS "Postal code Min",
    round(max("Postal Code"), 1)     AS "Postal code Max"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 24 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                        AS "Bucket",
    entity_id                                                                               AS "Entity Id",
    unit_of_measurement                                                                     AS "Unit Of Measurement",
    round(avg("Road Crash (BALLAJURA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810011)"), 1) AS "Road crash (ballajura, city of swan, metro north east, cad-id: 810011) Avg"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 25 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                        AS "Bucket",
    entity_id                                                                               AS "Entity Id",
    unit_of_measurement                                                                     AS "Unit Of Measurement",
    round(min("Road Crash (BALLAJURA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810011)"), 1) AS "Road crash (ballajura, city of swan, metro north east, cad-id: 810011) Min"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 26 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                        AS "Bucket",
    entity_id                                                                               AS "Entity Id",
    unit_of_measurement                                                                     AS "Unit Of Measurement",
    round(max("Road Crash (BALLAJURA, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 810011)"), 1) AS "Road crash (ballajura, city of swan, metro north east, cad-id: 810011) Max"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 27 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                          AS "Bucket",
    entity_id                                                                                 AS "Entity Id",
    unit_of_measurement                                                                       AS "Unit Of Measurement",
    round(avg("Road Crash (MORLEY, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 809968)"), 1) AS "Road crash (morley, city of bayswater, metro north east, cad-id: 809968) Avg"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 28 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                          AS "Bucket",
    entity_id                                                                                 AS "Entity Id",
    unit_of_measurement                                                                       AS "Unit Of Measurement",
    round(min("Road Crash (MORLEY, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 809968)"), 1) AS "Road crash (morley, city of bayswater, metro north east, cad-id: 809968) Min"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 29 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                          AS "Bucket",
    entity_id                                                                                 AS "Entity Id",
    unit_of_measurement                                                                       AS "Unit Of Measurement",
    round(max("Road Crash (MORLEY, CITY OF BAYSWATER, METRO NORTH EAST, CAD-ID: 809968)"), 1) AS "Road crash (morley, city of bayswater, metro north east, cad-id: 809968) Max"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 30 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                               AS "Bucket",
    entity_id                                                                                      AS "Entity Id",
    unit_of_measurement                                                                            AS "Unit Of Measurement",
    round(avg("Structure Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)"), 1) AS "Structure fire (henley brook, city of swan, metro north east, cad-id: 809994) Avg"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 31 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                               AS "Bucket",
    entity_id                                                                                      AS "Entity Id",
    unit_of_measurement                                                                            AS "Unit Of Measurement",
    round(min("Structure Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)"), 1) AS "Structure fire (henley brook, city of swan, metro north east, cad-id: 809994) Min"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 32 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)                                                               AS "Bucket",
    entity_id                                                                                      AS "Entity Id",
    unit_of_measurement                                                                            AS "Unit Of Measurement",
    round(max("Structure Fire (HENLEY BROOK, CITY OF SWAN, METRO NORTH EAST, CAD-ID: 809994)"), 1) AS "Structure fire (henley brook, city of swan, metro north east, cad-id: 809994) Max",
    round(avg("Sub Thoroughfare"), 1)                                                              AS "Sub thoroughfare Avg",
    round(min("Sub Thoroughfare"), 1)                                                              AS "Sub thoroughfare Min"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 33 of 36:
SELECT
    date_bin(INTERVAL '1 day', time)  AS "Bucket",
    entity_id                         AS "Entity Id",
    unit_of_measurement               AS "Unit Of Measurement",
    round(max("Sub Thoroughfare"), 1) AS "Sub thoroughfare Max",
    round(avg("Total"), 1)            AS "Total Avg",
    round(min("Total"), 1)            AS "Total Min",
    round(max("Total"), 1)            AS "Total Max",
    round(avg(bom_id), 1)             AS "Bom Id Avg",
    round(min(bom_id), 1)             AS "Bom Id Min",
    round(max(bom_id), 1)             AS "Bom Id Max",
    round(avg(date), 1)               AS "Date Avg",
    round(min(date), 1)               AS "Date Min",
    round(max(date), 1)               AS "Date Max"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 34 of 36:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    unit_of_measurement              AS "Unit Of Measurement",
    round(avg(distance), 1)          AS "Distance Avg",
    round(min(distance), 1)          AS "Distance Min",
    round(max(distance), 1)          AS "Distance Max",
    round(avg(issue_time), 1)        AS "Issue Time Avg",
    round(min(issue_time), 1)        AS "Issue Time Min",
    round(max(issue_time), 1)        AS "Issue Time Max",
    round(avg(next_issue_time), 1)   AS "Next Issue Time Avg",
    round(min(next_issue_time), 1)   AS "Next Issue Time Min"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 35 of 36:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    unit_of_measurement              AS "Unit Of Measurement",
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
-- part 36 of 36:
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
