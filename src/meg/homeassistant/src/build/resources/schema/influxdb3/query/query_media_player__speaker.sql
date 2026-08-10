--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- media_player__speaker [Home Assistant media_player__speaker] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 2:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(avg(is_volume_muted), 1)   AS "Is Volume Muted Avg",
    round(min(is_volume_muted), 1)   AS "Is Volume Muted Min",
    round(max(is_volume_muted), 1)   AS "Is Volume Muted Max",
    round(avg(media_channel), 1)     AS "Media Channel Avg",
    round(min(media_channel), 1)     AS "Media Channel Min",
    round(max(media_channel), 1)     AS "Media Channel Max",
    round(avg(media_duration), 1)    AS "Media Duration Avg"
FROM media_player__speaker
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM media_player__speaker) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- media_player__speaker [Home Assistant media_player__speaker] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 2 of 2:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(min(media_duration), 1)    AS "Media Duration Min",
    round(max(media_duration), 1)    AS "Media Duration Max",
    round(avg(value), 1)             AS "Value Avg",
    round(min(value), 1)             AS "Value Min",
    round(max(value), 1)             AS "Value Max",
    round(avg(volume_level), 1)      AS "Volume Level Avg",
    round(min(volume_level), 1)      AS "Volume Level Min",
    round(max(volume_level), 1)      AS "Volume Level Max"
FROM media_player__speaker
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM media_player__speaker) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
