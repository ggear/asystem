--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- sensor [Home Assistant sensor] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 5:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    unit_of_measurement                                      AS "Unit Of Measurement",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(color_fill), 1)                                AS "Color Fill Avg",
    round(min(color_fill), 1)                                AS "Color Fill Min",
    round(max(color_fill), 1)                                AS "Color Fill Max",
    count(color_fill)                                        AS "Color Fill Count",
    count(DISTINCT color_fill)                               AS "Color Fill Distinct"
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
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    unit_of_measurement                                      AS "Unit Of Measurement",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    last_value(color_fill_str ORDER BY time)                 AS "Color Fill Str",
    count(color_fill_str)                                    AS "Color Fill Str Count",
    count(DISTINCT color_fill_str)                           AS "Color Fill Str Distinct"
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
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    unit_of_measurement                                      AS "Unit Of Measurement",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(color_text), 1)                                AS "Color Text Avg",
    round(min(color_text), 1)                                AS "Color Text Min",
    round(max(color_text), 1)                                AS "Color Text Max",
    count(color_text)                                        AS "Color Text Count",
    count(DISTINCT color_text)                               AS "Color Text Distinct"
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
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    unit_of_measurement                                      AS "Unit Of Measurement",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    last_value(color_text_str ORDER BY time)                 AS "Color Text Str",
    count(color_text_str)                                    AS "Color Text Str Count",
    count(DISTINCT color_text_str)                           AS "Color Text Str Distinct",
    last_value(state ORDER BY time)                          AS "State",
    count(state)                                             AS "State Count",
    count(DISTINCT state)                                    AS "State Distinct"
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
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    unit_of_measurement                                      AS "Unit Of Measurement",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(value), 1)                                     AS "Value Avg",
    round(min(value), 1)                                     AS "Value Min",
    round(max(value), 1)                                     AS "Value Max",
    count(value)                                             AS "Value Count",
    count(DISTINCT value)                                    AS "Value Distinct",
    last_value(warnings_str ORDER BY time)                   AS "Warnings Str",
    count(warnings_str)                                      AS "Warnings Str Count",
    count(DISTINCT warnings_str)                             AS "Warnings Str Distinct"
FROM sensor
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;
