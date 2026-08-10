--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- declared vocabulary against what the service actually wrote, rows come back only on drift
SELECT
    'certificate/endpoint' AS relation,
    'verified'             AS measure,
    '15m'                  AS period,
    '-'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'certificate'
HAVING count(*) FILTER (WHERE column_name = 'verified') = 0
UNION ALL
SELECT
    'certificate/endpoint' AS relation,
    'expiry_days'          AS measure,
    '15m'                  AS period,
    'd'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'certificate'
HAVING count(*) FILTER (WHERE column_name = 'expiry_days') = 0
UNION ALL
SELECT
    'certificate/endpoint' AS relation,
    'validity_pct'         AS measure,
    '15m'                  AS period,
    '%'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'certificate'
HAVING count(*) FILTER (WHERE column_name = 'validity_pct') = 0
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
    AND column_name NOT IN ('endpoint', 'expiry_days', 'module', 'time', 'validity_pct', 'verified')
ORDER BY fault, measure;

SELECT
    'diagnosis/plugin' AS relation,
    'ok'               AS measure,
    '15m'              AS period,
    '-'                AS unit,
    'missing'          AS fault
FROM information_schema.columns
WHERE
    table_name = 'diagnosis'
HAVING count(*) FILTER (WHERE column_name = 'ok') = 0
UNION ALL
SELECT
    'diagnosis/plugin' AS relation,
    'score'            AS measure,
    '15m'              AS period,
    '-'                AS unit,
    'missing'          AS fault
FROM information_schema.columns
WHERE
    table_name = 'diagnosis'
HAVING count(*) FILTER (WHERE column_name = 'score') = 0
UNION ALL
SELECT
    'diagnosis'  AS relation,
    column_name  AS measure,
    '-'          AS period,
    '-'          AS unit,
    'undeclared' AS fault
FROM information_schema.columns
WHERE
    table_name = 'diagnosis'
    AND column_name NOT IN ('module', 'ok', 'plugin', 'score', 'time')
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
    'resolved'        AS measure,
    '15m'             AS period,
    '-'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'domain'
HAVING count(*) FILTER (WHERE column_name = 'resolved') = 0
UNION ALL
SELECT
    'domain/resolver' AS relation,
    'latency_ms'      AS measure,
    '15m'             AS period,
    'ms'              AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'domain'
HAVING count(*) FILTER (WHERE column_name = 'latency_ms') = 0
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
    AND column_name NOT IN ('latency_ms', 'module', 'ok', 'resolved', 'resolver', 'time')
ORDER BY fault, measure;

SELECT
    'ethernet/port' AS relation,
    'up'            AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'up') = 0
UNION ALL
SELECT
    'ethernet/port' AS relation,
    'speed_mbps'    AS measure,
    '15m'           AS period,
    'Mbps'          AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'speed_mbps') = 0
UNION ALL
SELECT
    'ethernet/port' AS relation,
    'full_duplex'   AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'full_duplex') = 0
UNION ALL
SELECT
    'ethernet/port' AS relation,
    'degraded'      AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'degraded') = 0
UNION ALL
SELECT
    'ethernet/port' AS relation,
    'errors'        AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
HAVING count(*) FILTER (WHERE column_name = 'errors') = 0
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
    AND column_name NOT IN ('degraded', 'errors', 'full_duplex', 'module', 'port', 'speed_mbps', 'time', 'up')
ORDER BY fault, measure;

SELECT
    'internet/target' AS relation,
    'reachable'       AS measure,
    '15m'             AS period,
    '-'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'internet'
HAVING count(*) FILTER (WHERE column_name = 'reachable') = 0
UNION ALL
SELECT
    'internet/target' AS relation,
    'loss_pct'        AS measure,
    '15m'             AS period,
    '%'               AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'internet'
HAVING count(*) FILTER (WHERE column_name = 'loss_pct') = 0
UNION ALL
SELECT
    'internet/target' AS relation,
    'rtt_ms'          AS measure,
    '15m'             AS period,
    'ms'              AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'internet'
HAVING count(*) FILTER (WHERE column_name = 'rtt_ms') = 0
UNION ALL
SELECT
    'internet/target' AS relation,
    'jitter_ms'       AS measure,
    '15m'             AS period,
    'ms'              AS unit,
    'missing'         AS fault
FROM information_schema.columns
WHERE
    table_name = 'internet'
HAVING count(*) FILTER (WHERE column_name = 'jitter_ms') = 0
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
    AND column_name NOT IN ('jitter_ms', 'loss_pct', 'module', 'reachable', 'rtt_ms', 'target', 'time')
ORDER BY fault, measure;

SELECT
    'weewx/console' AS relation,
    'fresh'         AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'weewx'
HAVING count(*) FILTER (WHERE column_name = 'fresh') = 0
UNION ALL
SELECT
    'weewx/console' AS relation,
    'quality_pct'   AS measure,
    '15m'           AS period,
    '%'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'weewx'
HAVING count(*) FILTER (WHERE column_name = 'quality_pct') = 0
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
    AND column_name NOT IN ('console', 'fresh', 'module', 'quality_pct', 'time')
ORDER BY fault, measure;

SELECT
    'wireless/accesspoint' AS relation,
    'up'                   AS measure,
    '15m'                  AS period,
    '-'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'wireless'
HAVING count(*) FILTER (WHERE column_name = 'up') = 0
UNION ALL
SELECT
    'wireless/accesspoint' AS relation,
    'experience_pct'       AS measure,
    '15m'                  AS period,
    '%'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'wireless'
HAVING count(*) FILTER (WHERE column_name = 'experience_pct') = 0
UNION ALL
SELECT
    'wireless/accesspoint' AS relation,
    'clients'              AS measure,
    '15m'                  AS period,
    '-'                    AS unit,
    'missing'              AS fault
FROM information_schema.columns
WHERE
    table_name = 'wireless'
HAVING count(*) FILTER (WHERE column_name = 'clients') = 0
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
    AND column_name NOT IN ('accesspoint', 'clients', 'experience_pct', 'module', 'time', 'up')
ORDER BY fault, measure;

SELECT
    'zigbee/device' AS relation,
    'available'     AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'zigbee'
HAVING count(*) FILTER (WHERE column_name = 'available') = 0
UNION ALL
SELECT
    'zigbee/device' AS relation,
    'coordinator'   AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'zigbee'
HAVING count(*) FILTER (WHERE column_name = 'coordinator') = 0
UNION ALL
SELECT
    'zigbee/device' AS relation,
    'lqi'           AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'zigbee'
HAVING count(*) FILTER (WHERE column_name = 'lqi') = 0
UNION ALL
SELECT
    'zigbee/device' AS relation,
    'weak'          AS measure,
    '15m'           AS period,
    '-'             AS unit,
    'missing'       AS fault
FROM information_schema.columns
WHERE
    table_name = 'zigbee'
HAVING count(*) FILTER (WHERE column_name = 'weak') = 0
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
    AND column_name NOT IN ('available', 'coordinator', 'device', 'lqi', 'module', 'time', 'weak')
ORDER BY fault, measure;
