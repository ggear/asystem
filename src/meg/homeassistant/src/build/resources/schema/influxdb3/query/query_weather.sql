--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- weather [Home Assistant weather] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 1:
SELECT
    date_bin(INTERVAL '1 day', time)    AS "Bucket",
    entity_id                           AS "Entity Id",
    round(avg(apparent_temperature), 1) AS "Apparent Temperature",
    round(avg(dew_point), 1)            AS "Dew Point",
    round(avg(humidity), 1)             AS "Humidity",
    round(avg(later_temp), 1)           AS "Later Temp",
    round(avg(now_temp), 1)             AS "Now Temp",
    round(avg(station_id), 1)           AS "Station Id",
    round(avg(sunrise), 1)              AS "Sunrise",
    round(avg(sunset), 1)               AS "Sunset",
    round(avg(temperature), 1)          AS "Temperature",
    round(avg(uv_end_time), 1)          AS "Uv End Time",
    round(avg(uv_index), 1)             AS "Uv Index",
    round(avg(uv_start_time), 1)        AS "Uv Start Time",
    round(avg(warning_count), 1)        AS "Warning Count",
    round(avg(wind_gust_speed), 1)      AS "Wind Gust Speed",
    round(avg(wind_speed), 1)           AS "Wind Speed"
FROM weather
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weather) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
