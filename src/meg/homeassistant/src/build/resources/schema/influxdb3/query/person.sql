--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- person [Home Assistant person] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 3:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(gps_accuracy), 1)                              AS "Gps Accuracy Avg",
    round(min(gps_accuracy), 1)                              AS "Gps Accuracy Min",
    round(max(gps_accuracy), 1)                              AS "Gps Accuracy Max",
    count(gps_accuracy)                                      AS "Gps Accuracy Count",
    count(DISTINCT gps_accuracy)                             AS "Gps Accuracy Distinct",
    round(avg(latitude), 1)                                  AS "Latitude Avg",
    round(min(latitude), 1)                                  AS "Latitude Min",
    round(max(latitude), 1)                                  AS "Latitude Max",
    count(latitude)                                          AS "Latitude Count",
    count(DISTINCT latitude)                                 AS "Latitude Distinct"
FROM person
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM person) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- person [Home Assistant person] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 2 of 3:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(longitude), 1)                                 AS "Longitude Avg",
    round(min(longitude), 1)                                 AS "Longitude Min",
    round(max(longitude), 1)                                 AS "Longitude Max",
    count(longitude)                                         AS "Longitude Count",
    count(DISTINCT longitude)                                AS "Longitude Distinct",
    last_value(state ORDER BY time)                          AS "State",
    count(state)                                             AS "State Count",
    count(DISTINCT state)                                    AS "State Distinct"
FROM person
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM person) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- person [Home Assistant person] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 3 of 3:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(value), 1)                                     AS "Value Avg",
    round(min(value), 1)                                     AS "Value Min",
    round(max(value), 1)                                     AS "Value Max",
    count(value)                                             AS "Value Count",
    count(DISTINCT value)                                    AS "Value Distinct"
FROM person
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM person) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
