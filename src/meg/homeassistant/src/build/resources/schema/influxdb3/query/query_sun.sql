--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- sun [Home Assistant sun] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(avg(azimuth), 1)           AS "Azimuth",
    round(avg(elevation), 1)         AS "Elevation",
    round(avg(next_dawn), 1)         AS "Next Dawn",
    round(avg(next_dusk), 1)         AS "Next Dusk",
    round(avg(next_rising), 1)       AS "Next Rising",
    round(avg(next_setting), 1)      AS "Next Setting",
    round(avg(rising), 1)            AS "Rising",
    round(avg(value), 1)             AS "Value"
FROM sun
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sun) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
