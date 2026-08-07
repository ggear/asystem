--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- declared vocabulary against what the service actually wrote, rows come back only on drift
SELECT
    'certificate/endpoint' AS relation,
    'ok'                   AS measure,
    '15m'                  AS period,
    '-'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'certificate'
HAVING count(*) FILTER (WHERE column_name = 'ok') = 0
UNION ALL
SELECT
    'certificate/endpoint' AS relation,
    'score'                AS measure,
    '15m'                  AS period,
    '-'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'certificate'
HAVING count(*) FILTER (WHERE column_name = 'score') = 0
UNION ALL
SELECT
    'certificate/endpoint' AS relation,
    'min_expiry_days'      AS measure,
    '15m'                  AS period,
    'd'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'certificate'
HAVING count(*) FILTER (WHERE column_name = 'min_expiry_days') = 0
UNION ALL
SELECT
    'certificate/endpoint' AS relation,
    'endpoints_total'      AS measure,
    '15m'                  AS period,
    '-'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'certificate'
HAVING count(*) FILTER (WHERE column_name = 'endpoints_total') = 0
UNION ALL
SELECT
    'certificate/endpoint' AS relation,
    'endpoints_failed'     AS measure,
    '15m'                  AS period,
    '-'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'certificate'
HAVING count(*) FILTER (WHERE column_name = 'endpoints_failed') = 0
UNION ALL
SELECT
    'certificate' AS relation,
    column_name   AS measure,
    '-'           AS period,
    '-'           AS unit,
    'undeclared'  AS fault
FROM information_schema.columns
WHERE
    table_name = 'certificate'
    AND column_name NOT IN ('endpoints_failed', 'endpoints_total', 'min_expiry_days', 'ok', 'score', 'time')
ORDER BY fault, measure;

SELECT
    'domain/resolver' AS relation,
    'ok'              AS measure,
    '15m'             AS period,
    '-'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'domain'
HAVING count(*) FILTER (WHERE column_name = 'ok') = 0
UNION ALL
SELECT
    'domain/resolver' AS relation,
    'score'           AS measure,
    '15m'             AS period,
    '-'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'domain'
HAVING count(*) FILTER (WHERE column_name = 'score') = 0
UNION ALL
SELECT
    'domain/resolver' AS relation,
    'resolvers_total' AS measure,
    '15m'             AS period,
    '-'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'domain'
HAVING count(*) FILTER (WHERE column_name = 'resolvers_total') = 0
UNION ALL
SELECT
    'domain/resolver' AS relation,
    'resolvers_ok'    AS measure,
    '15m'             AS period,
    '-'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'domain'
HAVING count(*) FILTER (WHERE column_name = 'resolvers_ok') = 0
UNION ALL
SELECT
    'domain/resolver'  AS relation,
    'resolvers_failed' AS measure,
    '15m'              AS period,
    '-'                AS unit,
    'missing'          AS fault
FROM information_schema.columns
WHERE
    table_name = 'domain'
HAVING count(*) FILTER (WHERE column_name = 'resolvers_failed') = 0
UNION ALL
SELECT
    'domain'     AS relation,
    column_name  AS measure,
    '-'          AS period,
    '-'          AS unit,
    'undeclared' AS fault
FROM information_schema.columns
WHERE
    table_name = 'domain'
    AND column_name NOT IN ('ok', 'resolvers_failed', 'resolvers_ok', 'resolvers_total', 'score', 'time')
ORDER BY fault, measure;

SELECT
    'ethernet/port' AS relation,
    'score'         AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'score') = 0
UNION ALL
SELECT
    'ethernet/port' AS relation,
    'ok'            AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'ok') = 0
UNION ALL
SELECT
    'ethernet/port' AS relation,
    'ports_total'   AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'ports_total') = 0
UNION ALL
SELECT
    'ethernet/port' AS relation,
    'ports_ok'      AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'ports_ok') = 0
UNION ALL
SELECT
    'ethernet/port'  AS relation,
    'ports_degraded' AS measure,
    '15m'            AS period,
    '-'              AS unit,
    'missing'        AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'ports_degraded') = 0
UNION ALL
SELECT
    'ethernet/port' AS relation,
    'ports_errored' AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'ports_errored') = 0
UNION ALL
SELECT
    'ethernet'   AS relation,
    column_name  AS measure,
    '-'          AS period,
    '-'          AS unit,
    'undeclared' AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
    AND column_name NOT IN ('ok', 'ports_degraded', 'ports_errored', 'ports_ok', 'ports_total', 'score', 'time')
ORDER BY fault, measure;

SELECT
    'internet/gateway' AS relation,
    'ok'               AS measure,
    '15m'              AS period,
    '-'                AS unit,
    'missing'          AS fault
FROM information_schema.columns
WHERE
    table_name = 'internet'
HAVING count(*) FILTER (WHERE column_name = 'ok') = 0
UNION ALL
SELECT
    'internet/gateway' AS relation,
    'score'            AS measure,
    '15m'              AS period,
    '-'                AS unit,
    'missing'          AS fault
FROM information_schema.columns
WHERE
    table_name = 'internet'
HAVING count(*) FILTER (WHERE column_name = 'score') = 0
UNION ALL
SELECT
    'internet/gateway' AS relation,
    'targets_total'    AS measure,
    '15m'              AS period,
    '-'                AS unit,
    'missing'          AS fault
FROM information_schema.columns
WHERE
    table_name = 'internet'
HAVING count(*) FILTER (WHERE column_name = 'targets_total') = 0
UNION ALL
SELECT
    'internet/gateway' AS relation,
    'targets_ok'       AS measure,
    '15m'              AS period,
    '-'                AS unit,
    'missing'          AS fault
FROM information_schema.columns
WHERE
    table_name = 'internet'
HAVING count(*) FILTER (WHERE column_name = 'targets_ok') = 0
UNION ALL
SELECT
    'internet/gateway' AS relation,
    'avg_loss_pct'     AS measure,
    '15m'              AS period,
    '%'                AS unit,
    'missing'          AS fault
FROM information_schema.columns
WHERE
    table_name = 'internet'
HAVING count(*) FILTER (WHERE column_name = 'avg_loss_pct') = 0
UNION ALL
SELECT
    'internet/gateway' AS relation,
    'avg_rtt_ms'       AS measure,
    '15m'              AS period,
    'ms'               AS unit,
    'missing'          AS fault
FROM information_schema.columns
WHERE
    table_name = 'internet'
HAVING count(*) FILTER (WHERE column_name = 'avg_rtt_ms') = 0
UNION ALL
SELECT
    'internet/gateway' AS relation,
    'avg_jitter_ms'    AS measure,
    '15m'              AS period,
    'ms'               AS unit,
    'missing'          AS fault
FROM information_schema.columns
WHERE
    table_name = 'internet'
HAVING count(*) FILTER (WHERE column_name = 'avg_jitter_ms') = 0
UNION ALL
SELECT
    'internet/gateway' AS relation,
    'gateway_ok'       AS measure,
    '15m'              AS period,
    '-'                AS unit,
    'missing'          AS fault
FROM information_schema.columns
WHERE
    table_name = 'internet'
HAVING count(*) FILTER (WHERE column_name = 'gateway_ok') = 0
UNION ALL
SELECT
    'internet'   AS relation,
    column_name  AS measure,
    '-'          AS period,
    '-'          AS unit,
    'undeclared' AS fault
FROM information_schema.columns
WHERE
    table_name = 'internet'
    AND column_name NOT IN (
        'avg_jitter_ms', 'avg_loss_pct', 'avg_rtt_ms', 'gateway_ok', 'ok', 'score',
        'targets_ok', 'targets_total', 'time'
    )
ORDER BY fault, measure;

SELECT
    'weewx/console' AS relation,
    'ok'            AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'weewx'
HAVING count(*) FILTER (WHERE column_name = 'ok') = 0
UNION ALL
SELECT
    'weewx/console' AS relation,
    'score'         AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'weewx'
HAVING count(*) FILTER (WHERE column_name = 'score') = 0
UNION ALL
SELECT
    'weewx'      AS relation,
    column_name  AS measure,
    '-'          AS period,
    '-'          AS unit,
    'undeclared' AS fault
FROM information_schema.columns
WHERE
    table_name = 'weewx'
    AND column_name NOT IN ('ok', 'score', 'time')
ORDER BY fault, measure;

SELECT
    'wireless/accesspoint' AS relation,
    'ok'                   AS measure,
    '15m'                  AS period,
    '-'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'wireless'
HAVING count(*) FILTER (WHERE column_name = 'ok') = 0
UNION ALL
SELECT
    'wireless/accesspoint' AS relation,
    'score'                AS measure,
    '15m'                  AS period,
    '-'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'wireless'
HAVING count(*) FILTER (WHERE column_name = 'score') = 0
UNION ALL
SELECT
    'wireless/accesspoint' AS relation,
    'aps_total'            AS measure,
    '15m'                  AS period,
    '-'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'wireless'
HAVING count(*) FILTER (WHERE column_name = 'aps_total') = 0
UNION ALL
SELECT
    'wireless/accesspoint' AS relation,
    'aps_ok'               AS measure,
    '15m'                  AS period,
    '-'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'wireless'
HAVING count(*) FILTER (WHERE column_name = 'aps_ok') = 0
UNION ALL
SELECT
    'wireless/accesspoint' AS relation,
    'avg_experience_pct'   AS measure,
    '15m'                  AS period,
    '%'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'wireless'
HAVING count(*) FILTER (WHERE column_name = 'avg_experience_pct') = 0
UNION ALL
SELECT
    'wireless'   AS relation,
    column_name  AS measure,
    '-'          AS period,
    '-'          AS unit,
    'undeclared' AS fault
FROM information_schema.columns
WHERE
    table_name = 'wireless'
    AND column_name NOT IN ('aps_ok', 'aps_total', 'avg_experience_pct', 'ok', 'score', 'time')
ORDER BY fault, measure;

SELECT
    'zigbee/bridge' AS relation,
    'ok'            AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'zigbee'
HAVING count(*) FILTER (WHERE column_name = 'ok') = 0
UNION ALL
SELECT
    'zigbee/bridge' AS relation,
    'score'         AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'zigbee'
HAVING count(*) FILTER (WHERE column_name = 'score') = 0
UNION ALL
SELECT
    'zigbee/bridge' AS relation,
    'devices_total' AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'zigbee'
HAVING count(*) FILTER (WHERE column_name = 'devices_total') = 0
UNION ALL
SELECT
    'zigbee/bridge' AS relation,
    'devices_ok'    AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'zigbee'
HAVING count(*) FILTER (WHERE column_name = 'devices_ok') = 0
UNION ALL
SELECT
    'zigbee/bridge' AS relation,
    'devices_weak'  AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'zigbee'
HAVING count(*) FILTER (WHERE column_name = 'devices_weak') = 0
UNION ALL
SELECT
    'zigbee/bridge' AS relation,
    'avg_lqi'       AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'zigbee'
HAVING count(*) FILTER (WHERE column_name = 'avg_lqi') = 0
UNION ALL
SELECT
    'zigbee'     AS relation,
    column_name  AS measure,
    '-'          AS period,
    '-'          AS unit,
    'undeclared' AS fault
FROM information_schema.columns
WHERE
    table_name = 'zigbee'
    AND column_name NOT IN ('avg_lqi', 'devices_ok', 'devices_total', 'devices_weak', 'ok', 'score', 'time')
ORDER BY fault, measure;
