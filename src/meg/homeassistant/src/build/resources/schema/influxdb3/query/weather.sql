--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- weather [Home Assistant weather] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 2:
SELECT
    date_bin(INTERVAL '1 day', time)          AS "Bucket",
    entity_id                                 AS "Entity Id",
    round(avg(apparent_temperature), 1)       AS "Apparent Temperature",
    round(avg(dew_point), 1)                  AS "Dew Point",
    last_value(fire_danger_str ORDER BY time) AS "Fire Danger Str",
    round(avg(humidity), 1)                   AS "Humidity",
    last_value(later_label_str ORDER BY time) AS "Later Label Str",
    round(avg(later_temp), 1)                 AS "Later Temp",
    last_value(now_label_str ORDER BY time)   AS "Now Label Str",
    round(avg(now_temp), 1)                   AS "Now Temp",
    last_value(state ORDER BY time)           AS "State",
    round(avg(sunrise), 1)                    AS "Sunrise",
    last_value(sunrise_str ORDER BY time)     AS "Sunrise Str",
    round(avg(sunset), 1)                     AS "Sunset",
    last_value(sunset_str ORDER BY time)      AS "Sunset Str",
    round(avg(temperature), 1)                AS "Temperature",
    last_value(uv_category_str ORDER BY time) AS "Uv Category Str",
    round(avg(uv_end_time), 1)                AS "Uv End Time",
    last_value(uv_end_time_str ORDER BY time) AS "Uv End Time Str",
    round(avg(uv_index), 1)                   AS "Uv Index"
FROM weather
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weather) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- weather [Home Assistant weather] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 2 of 2:
SELECT
    date_bin(INTERVAL '1 day', time)            AS "Bucket",
    entity_id                                   AS "Entity Id",
    round(avg(uv_start_time), 1)                AS "Uv Start Time",
    last_value(uv_start_time_str ORDER BY time) AS "Uv Start Time Str",
    round(avg(warning_count), 1)                AS "Warning Count",
    last_value(wind_bearing_str ORDER BY time)  AS "Wind Bearing Str",
    round(avg(wind_gust_speed), 1)              AS "Wind Gust Speed",
    round(avg(wind_speed), 1)                   AS "Wind Speed"
FROM weather
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weather) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
