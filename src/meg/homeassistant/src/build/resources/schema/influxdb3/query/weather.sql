--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- weather [Home Assistant weather] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 1 of 12:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(apparent_temperature), 1)                      AS "Apparent Temperature Avg",
    round(min(apparent_temperature), 1)                      AS "Apparent Temperature Min",
    round(max(apparent_temperature), 1)                      AS "Apparent Temperature Max",
    count(apparent_temperature)                              AS "Apparent Temperature Count",
    count(DISTINCT apparent_temperature)                     AS "Apparent Temperature Distinct"
FROM weather
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weather) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- weather [Home Assistant weather] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 2 of 12:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(dew_point), 1)                                 AS "Dew Point Avg",
    round(min(dew_point), 1)                                 AS "Dew Point Min",
    round(max(dew_point), 1)                                 AS "Dew Point Max",
    count(dew_point)                                         AS "Dew Point Count",
    count(DISTINCT dew_point)                                AS "Dew Point Distinct",
    last_value(fire_danger_str ORDER BY time)                AS "Fire Danger Str",
    count(fire_danger_str)                                   AS "Fire Danger Str Count",
    count(DISTINCT fire_danger_str)                          AS "Fire Danger Str Distinct"
FROM weather
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weather) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- weather [Home Assistant weather] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 3 of 12:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(humidity), 1)                                  AS "Humidity Avg",
    round(min(humidity), 1)                                  AS "Humidity Min",
    round(max(humidity), 1)                                  AS "Humidity Max",
    count(humidity)                                          AS "Humidity Count",
    count(DISTINCT humidity)                                 AS "Humidity Distinct",
    last_value(later_label_str ORDER BY time)                AS "Later Label Str",
    count(later_label_str)                                   AS "Later Label Str Count",
    count(DISTINCT later_label_str)                          AS "Later Label Str Distinct"
FROM weather
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weather) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- weather [Home Assistant weather] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 4 of 12:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(later_temp), 1)                                AS "Later Temp Avg",
    round(min(later_temp), 1)                                AS "Later Temp Min",
    round(max(later_temp), 1)                                AS "Later Temp Max",
    count(later_temp)                                        AS "Later Temp Count",
    count(DISTINCT later_temp)                               AS "Later Temp Distinct",
    last_value(now_label_str ORDER BY time)                  AS "Now Label Str",
    count(now_label_str)                                     AS "Now Label Str Count",
    count(DISTINCT now_label_str)                            AS "Now Label Str Distinct"
FROM weather
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weather) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- weather [Home Assistant weather] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 5 of 12:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(now_temp), 1)                                  AS "Now Temp Avg",
    round(min(now_temp), 1)                                  AS "Now Temp Min",
    round(max(now_temp), 1)                                  AS "Now Temp Max",
    count(now_temp)                                          AS "Now Temp Count",
    count(DISTINCT now_temp)                                 AS "Now Temp Distinct",
    last_value(state ORDER BY time)                          AS "State",
    count(state)                                             AS "State Count",
    count(DISTINCT state)                                    AS "State Distinct"
FROM weather
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weather) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- weather [Home Assistant weather] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 6 of 12:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(sunrise), 1)                                   AS "Sunrise Avg",
    round(min(sunrise), 1)                                   AS "Sunrise Min",
    round(max(sunrise), 1)                                   AS "Sunrise Max",
    count(sunrise)                                           AS "Sunrise Count",
    count(DISTINCT sunrise)                                  AS "Sunrise Distinct",
    last_value(sunrise_str ORDER BY time)                    AS "Sunrise Str",
    count(sunrise_str)                                       AS "Sunrise Str Count",
    count(DISTINCT sunrise_str)                              AS "Sunrise Str Distinct"
FROM weather
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weather) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- weather [Home Assistant weather] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 7 of 12:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(sunset), 1)                                    AS "Sunset Avg",
    round(min(sunset), 1)                                    AS "Sunset Min",
    round(max(sunset), 1)                                    AS "Sunset Max",
    count(sunset)                                            AS "Sunset Count",
    count(DISTINCT sunset)                                   AS "Sunset Distinct",
    last_value(sunset_str ORDER BY time)                     AS "Sunset Str",
    count(sunset_str)                                        AS "Sunset Str Count",
    count(DISTINCT sunset_str)                               AS "Sunset Str Distinct"
FROM weather
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weather) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- weather [Home Assistant weather] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 8 of 12:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(temperature), 1)                               AS "Temperature Avg",
    round(min(temperature), 1)                               AS "Temperature Min",
    round(max(temperature), 1)                               AS "Temperature Max",
    count(temperature)                                       AS "Temperature Count",
    count(DISTINCT temperature)                              AS "Temperature Distinct",
    last_value(uv_category_str ORDER BY time)                AS "Uv Category Str",
    count(uv_category_str)                                   AS "Uv Category Str Count",
    count(DISTINCT uv_category_str)                          AS "Uv Category Str Distinct"
FROM weather
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weather) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- weather [Home Assistant weather] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 9 of 12:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(uv_index), 1)                                  AS "Uv Index Avg",
    round(min(uv_index), 1)                                  AS "Uv Index Min",
    round(max(uv_index), 1)                                  AS "Uv Index Max",
    count(uv_index)                                          AS "Uv Index Count",
    count(DISTINCT uv_index)                                 AS "Uv Index Distinct",
    round(avg(warning_count), 1)                             AS "Warning Count Avg",
    round(min(warning_count), 1)                             AS "Warning Count Min",
    round(max(warning_count), 1)                             AS "Warning Count Max",
    count(warning_count)                                     AS "Warning Count Count",
    count(DISTINCT warning_count)                            AS "Warning Count Distinct"
FROM weather
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weather) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- weather [Home Assistant weather] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 10 of 12:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    last_value(wind_bearing_str ORDER BY time)               AS "Wind Bearing Str",
    count(wind_bearing_str)                                  AS "Wind Bearing Str Count",
    count(DISTINCT wind_bearing_str)                         AS "Wind Bearing Str Distinct"
FROM weather
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weather) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- weather [Home Assistant weather] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 11 of 12:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(wind_gust_speed), 1)                           AS "Wind Gust Speed Avg",
    round(min(wind_gust_speed), 1)                           AS "Wind Gust Speed Min",
    round(max(wind_gust_speed), 1)                           AS "Wind Gust Speed Max",
    count(wind_gust_speed)                                   AS "Wind Gust Speed Count",
    count(DISTINCT wind_gust_speed)                          AS "Wind Gust Speed Distinct"
FROM weather
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weather) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;

-- weather [Home Assistant weather] every <on-change>, bucketed [1 day] across the newest two buckets
-- part 12 of 12:
SELECT
    date_bin(INTERVAL '1 day', time + INTERVAL '480 minute') AS "Bucket",
    entity_id                                                AS "Entity Id",
    count(*)                                                 AS "Rows",
    min(time) + INTERVAL '480 minute'                        AS "Oldest",
    max(time) + INTERVAL '480 minute'                        AS "Newest",
    round(avg(wind_speed), 1)                                AS "Wind Speed Avg",
    round(min(wind_speed), 1)                                AS "Wind Speed Min",
    round(max(wind_speed), 1)                                AS "Wind Speed Max",
    count(wind_speed)                                        AS "Wind Speed Count",
    count(DISTINCT wind_speed)                               AS "Wind Speed Distinct"
FROM weather
WHERE
    module = 'homeassistant'
    AND time >= now() - INTERVAL '100 day'
    AND time >= (SELECT max(time) FROM weather) - INTERVAL '1 day'
GROUP BY "Bucket", entity_id
ORDER BY "Bucket", entity_id;
