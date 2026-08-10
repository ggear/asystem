--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- sun [Home Assistant sun] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 3:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(avg(azimuth), 1)           AS "Azimuth Avg",
    round(min(azimuth), 1)           AS "Azimuth Min",
    round(max(azimuth), 1)           AS "Azimuth Max",
    round(avg(elevation), 1)         AS "Elevation Avg",
    round(min(elevation), 1)         AS "Elevation Min",
    round(max(elevation), 1)         AS "Elevation Max",
    round(avg(next_dawn), 1)         AS "Next Dawn Avg",
    round(min(next_dawn), 1)         AS "Next Dawn Min",
    round(max(next_dawn), 1)         AS "Next Dawn Max",
    round(avg(next_dusk), 1)         AS "Next Dusk Avg"
FROM sun
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sun) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- sun [Home Assistant sun] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 2 of 3:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(min(next_dusk), 1)         AS "Next Dusk Min",
    round(max(next_dusk), 1)         AS "Next Dusk Max",
    round(avg(next_rising), 1)       AS "Next Rising Avg",
    round(min(next_rising), 1)       AS "Next Rising Min",
    round(max(next_rising), 1)       AS "Next Rising Max",
    round(avg(next_setting), 1)      AS "Next Setting Avg",
    round(min(next_setting), 1)      AS "Next Setting Min",
    round(max(next_setting), 1)      AS "Next Setting Max",
    round(avg(rising), 1)            AS "Rising Avg"
FROM sun
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sun) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- sun [Home Assistant sun] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 3 of 3:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(min(rising), 1)            AS "Rising Min",
    round(max(rising), 1)            AS "Rising Max",
    round(avg(value), 1)             AS "Value Avg",
    round(min(value), 1)             AS "Value Min",
    round(max(value), 1)             AS "Value Max"
FROM sun
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sun) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
