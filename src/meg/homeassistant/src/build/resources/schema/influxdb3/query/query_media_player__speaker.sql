--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- media_player__speaker [Home Assistant media_player__speaker] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(avg(is_volume_muted), 1)   AS "Is Volume Muted",
    round(avg(media_album_name), 1)  AS "Media Album Name",
    round(avg(media_channel), 1)     AS "Media Channel",
    round(avg(media_duration), 1)    AS "Media Duration",
    round(avg(media_title), 1)       AS "Media Title",
    round(avg(value), 1)             AS "Value",
    round(avg(volume_level), 1)      AS "Volume Level"
FROM media_player__speaker
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM media_player__speaker) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
