--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- sensor__energy [Home Assistant sensor__energy] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    unit_of_measurement              AS "Unit Of Measurement",
    round(avg(last_valid_state), 1)  AS "Last Valid State",
    round(avg(next_reset), 1)        AS "Next Reset",
    round(avg(value), 1)             AS "Value"
FROM sensor__energy
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM sensor__energy) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id, unit_of_measurement
ORDER BY "Bucket", entity_id, unit_of_measurement;
