--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- weather [Home Assistant weather] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 6:
SELECT
    date_bin(INTERVAL '1 day', time)    AS "Bucket",
    entity_id                           AS "Entity Id",
    round(avg(apparent_temperature), 1) AS "Apparent Temperature Avg",
    round(min(apparent_temperature), 1) AS "Apparent Temperature Min",
    round(max(apparent_temperature), 1) AS "Apparent Temperature Max",
    round(avg(dew_point), 1)            AS "Dew Point Avg",
    round(min(dew_point), 1)            AS "Dew Point Min",
    round(max(dew_point), 1)            AS "Dew Point Max",
    round(avg(humidity), 1)             AS "Humidity Avg",
    round(min(humidity), 1)             AS "Humidity Min"
FROM weather
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weather) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- weather [Home Assistant weather] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 2 of 6:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(max(humidity), 1)          AS "Humidity Max",
    round(avg(later_temp), 1)        AS "Later Temp Avg",
    round(min(later_temp), 1)        AS "Later Temp Min",
    round(max(later_temp), 1)        AS "Later Temp Max",
    round(avg(now_temp), 1)          AS "Now Temp Avg",
    round(min(now_temp), 1)          AS "Now Temp Min",
    round(max(now_temp), 1)          AS "Now Temp Max",
    round(avg(station_id), 1)        AS "Station Id Avg",
    round(min(station_id), 1)        AS "Station Id Min"
FROM weather
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weather) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- weather [Home Assistant weather] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 3 of 6:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(max(station_id), 1)        AS "Station Id Max",
    round(avg(sunrise), 1)           AS "Sunrise Avg",
    round(min(sunrise), 1)           AS "Sunrise Min",
    round(max(sunrise), 1)           AS "Sunrise Max",
    round(avg(sunset), 1)            AS "Sunset Avg",
    round(min(sunset), 1)            AS "Sunset Min",
    round(max(sunset), 1)            AS "Sunset Max",
    round(avg(temperature), 1)       AS "Temperature Avg",
    round(min(temperature), 1)       AS "Temperature Min",
    round(max(temperature), 1)       AS "Temperature Max"
FROM weather
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weather) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- weather [Home Assistant weather] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 4 of 6:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(avg(uv_end_time), 1)       AS "Uv End Time Avg",
    round(min(uv_end_time), 1)       AS "Uv End Time Min",
    round(max(uv_end_time), 1)       AS "Uv End Time Max",
    round(avg(uv_index), 1)          AS "Uv Index Avg",
    round(min(uv_index), 1)          AS "Uv Index Min",
    round(max(uv_index), 1)          AS "Uv Index Max",
    round(avg(uv_start_time), 1)     AS "Uv Start Time Avg",
    round(min(uv_start_time), 1)     AS "Uv Start Time Min",
    round(max(uv_start_time), 1)     AS "Uv Start Time Max"
FROM weather
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weather) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- weather [Home Assistant weather] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 5 of 6:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(avg(warning_count), 1)     AS "Warning Count Avg",
    round(min(warning_count), 1)     AS "Warning Count Min",
    round(max(warning_count), 1)     AS "Warning Count Max",
    round(avg(wind_gust_speed), 1)   AS "Wind Gust Speed Avg",
    round(min(wind_gust_speed), 1)   AS "Wind Gust Speed Min",
    round(max(wind_gust_speed), 1)   AS "Wind Gust Speed Max",
    round(avg(wind_speed), 1)        AS "Wind Speed Avg"
FROM weather
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weather) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- weather [Home Assistant weather] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 6 of 6:
SELECT
    date_bin(INTERVAL '1 day', time) AS "Bucket",
    entity_id                        AS "Entity Id",
    round(min(wind_speed), 1)        AS "Wind Speed Min",
    round(max(wind_speed), 1)        AS "Wind Speed Max"
FROM weather
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weather) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
