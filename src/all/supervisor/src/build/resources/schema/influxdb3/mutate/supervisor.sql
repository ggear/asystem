--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- backfill [warn_temperature] from the renamed [warn_temperature_of_max], one line of protocol per row
SELECT
    'supervisor' ||
            ',module=' || module ||
            ',host=' || host ||
            ' warn_temperature=' || CAST(CAST(warn_temperature_of_max AS BIGINT) AS VARCHAR) || 'i' ||
            ' ' || CAST(CAST(time AS BIGINT) AS VARCHAR) AS line
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
    AND warn_temperature_of_max IS NOT NULL
ORDER BY time;

-- backfill [warn_temperature_trend] from the renamed [warn_temperature_of_max_trend], one line of protocol per row
SELECT
    'supervisor' ||
            ',module=' || module ||
            ',host=' || host ||
            ' warn_temperature_trend=' || CAST(CAST(warn_temperature_of_max_trend AS BIGINT) AS VARCHAR) || 'i' ||
            ' ' || CAST(CAST(time AS BIGINT) AS VARCHAR) AS line
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
    AND warn_temperature_of_max_trend IS NOT NULL
ORDER BY time;

-- backfill [spin_fan_speed] from the renamed [spin_fan_speed_of_max], one line of protocol per row
SELECT
    'supervisor' ||
            ',module=' || module ||
            ',host=' || host ||
            ' spin_fan_speed=' || CAST(CAST(spin_fan_speed_of_max AS BIGINT) AS VARCHAR) || 'i' ||
            ' ' || CAST(CAST(time AS BIGINT) AS VARCHAR) AS line
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
    AND spin_fan_speed_of_max IS NOT NULL
ORDER BY time;

-- backfill [spin_fan_speed_trend] from the renamed [spin_fan_speed_of_max_trend], one line of protocol per row
SELECT
    'supervisor' ||
            ',module=' || module ||
            ',host=' || host ||
            ' spin_fan_speed_trend=' || CAST(CAST(spin_fan_speed_of_max_trend AS BIGINT) AS VARCHAR) || 'i' ||
            ' ' || CAST(CAST(time AS BIGINT) AS VARCHAR) AS line
FROM supervisor
WHERE
    module = 'supervisor'
    AND host IS NOT NULL
    AND service IS NULL
    AND spin_fan_speed_of_max_trend IS NOT NULL
ORDER BY time;
