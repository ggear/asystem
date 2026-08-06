--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- every column in every measurement is declared, rows come back only on drift
SELECT
    'certs' AS measurement,
    column_name
FROM information_schema.columns
WHERE
    table_name = 'certs'
    AND column_name NOT IN ('endpoints_failed', 'endpoints_total', 'min_expiry_days', 'ok', 'score', 'time')
ORDER BY column_name;

SELECT
    'domain' AS measurement,
    column_name
FROM information_schema.columns
WHERE
    table_name = 'domain'
    AND column_name NOT IN ('ok', 'resolvers_failed', 'resolvers_ok', 'resolvers_total', 'score', 'time')
ORDER BY column_name;

SELECT
    'ethernet' AS measurement,
    column_name
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
    AND column_name NOT IN ('ok', 'ports_degraded', 'ports_errored', 'ports_ok', 'ports_total', 'score', 'time')
ORDER BY column_name;

SELECT
    'internet' AS measurement,
    column_name
FROM information_schema.columns
WHERE
    table_name = 'internet'
    AND column_name NOT IN (
        'avg_jitter_ms', 'avg_loss_pct', 'avg_rtt_ms', 'gateway_ok', 'ok', 'score',
        'targets_ok', 'targets_total', 'time'
    )
ORDER BY column_name;

SELECT
    'weewx' AS measurement,
    column_name
FROM information_schema.columns
WHERE
    table_name = 'weewx'
    AND column_name NOT IN ('ok', 'score', 'time')
ORDER BY column_name;

SELECT
    'wireless' AS measurement,
    column_name
FROM information_schema.columns
WHERE
    table_name = 'wireless'
    AND column_name NOT IN ('aps_ok', 'aps_total', 'avg_experience_pct', 'ok', 'score', 'time')
ORDER BY column_name;

SELECT
    'zigbee' AS measurement,
    column_name
FROM information_schema.columns
WHERE
    table_name = 'zigbee'
    AND column_name NOT IN ('avg_lqi', 'devices_ok', 'devices_total', 'devices_weak', 'ok', 'score', 'time')
ORDER BY column_name;
