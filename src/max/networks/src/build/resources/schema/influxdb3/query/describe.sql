--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- dimensions
SELECT
    'certificate/endpoint' AS relation,
    '-'                    AS dimension,
    5                      AS measures,
    '15m'                  AS cadence,
    count(*)               AS rows,
    min(time)              AS oldest,
    max(time)              AS newest
FROM certificate
UNION ALL
SELECT
    'domain/resolver' AS relation,
    '-'               AS dimension,
    5                 AS measures,
    '15m'             AS cadence,
    count(*)          AS rows,
    min(time)         AS oldest,
    max(time)         AS newest
FROM domain
UNION ALL
SELECT
    'ethernet/port' AS relation,
    '-'             AS dimension,
    6               AS measures,
    '15m'           AS cadence,
    count(*)        AS rows,
    min(time)       AS oldest,
    max(time)       AS newest
FROM ethernet
UNION ALL
SELECT
    'internet/gateway' AS relation,
    '-'                AS dimension,
    8                  AS measures,
    '15m'              AS cadence,
    count(*)           AS rows,
    min(time)          AS oldest,
    max(time)          AS newest
FROM internet
UNION ALL
SELECT
    'weewx/console' AS relation,
    '-'             AS dimension,
    2               AS measures,
    '15m'           AS cadence,
    count(*)        AS rows,
    min(time)       AS oldest,
    max(time)       AS newest
FROM weewx
UNION ALL
SELECT
    'wireless/accesspoint' AS relation,
    '-'                    AS dimension,
    5                      AS measures,
    '15m'                  AS cadence,
    count(*)               AS rows,
    min(time)              AS oldest,
    max(time)              AS newest
FROM wireless
UNION ALL
SELECT
    'zigbee/bridge' AS relation,
    '-'             AS dimension,
    6               AS measures,
    '15m'           AS cadence,
    count(*)        AS rows,
    min(time)       AS oldest,
    max(time)       AS newest
FROM zigbee
ORDER BY rows DESC;

-- measures
SELECT
    'certificate/endpoint'                                   AS relation,
    'ok'                                                     AS measure,
    'bool'                                                   AS kind,
    '-'                                                      AS unit,
    '15m'                                                    AS period,
    count(ok)                                                AS rows,
    CAST(min(time) FILTER (WHERE ok IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE ok IS NOT NULL) AS VARCHAR) AS newest
FROM certificate
UNION ALL
SELECT
    'certificate/endpoint'                                      AS relation,
    'score'                                                     AS measure,
    'int'                                                       AS kind,
    '-'                                                         AS unit,
    '15m'                                                       AS period,
    count(score)                                                AS rows,
    CAST(min(time) FILTER (WHERE score IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE score IS NOT NULL) AS VARCHAR) AS newest
FROM certificate
UNION ALL
SELECT
    'certificate/endpoint'                                                AS relation,
    'min_expiry_days'                                                     AS measure,
    'float'                                                               AS kind,
    'd'                                                                   AS unit,
    '15m'                                                                 AS period,
    count(min_expiry_days)                                                AS rows,
    CAST(min(time) FILTER (WHERE min_expiry_days IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE min_expiry_days IS NOT NULL) AS VARCHAR) AS newest
FROM certificate
UNION ALL
SELECT
    'certificate/endpoint'                                                AS relation,
    'endpoints_total'                                                     AS measure,
    'int'                                                                 AS kind,
    '-'                                                                   AS unit,
    '15m'                                                                 AS period,
    count(endpoints_total)                                                AS rows,
    CAST(min(time) FILTER (WHERE endpoints_total IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE endpoints_total IS NOT NULL) AS VARCHAR) AS newest
FROM certificate
UNION ALL
SELECT
    'certificate/endpoint'                                                 AS relation,
    'endpoints_failed'                                                     AS measure,
    'int'                                                                  AS kind,
    '-'                                                                    AS unit,
    '15m'                                                                  AS period,
    count(endpoints_failed)                                                AS rows,
    CAST(min(time) FILTER (WHERE endpoints_failed IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE endpoints_failed IS NOT NULL) AS VARCHAR) AS newest
FROM certificate
UNION ALL
SELECT
    '-'                   AS relation,
    column_name           AS measure,
    '-'                   AS kind,
    '-'                   AS unit,
    '-'                   AS period,
    CAST(NULL AS BIGINT)  AS rows,
    CAST(NULL AS VARCHAR) AS oldest,
    CAST(NULL AS VARCHAR) AS newest
FROM information_schema.columns
WHERE
    table_name = 'certificate'
    AND column_name NOT IN ('endpoints_failed', 'endpoints_total', 'min_expiry_days', 'ok', 'score', 'time')
UNION ALL
SELECT
    'domain/resolver'                                        AS relation,
    'ok'                                                     AS measure,
    'bool'                                                   AS kind,
    '-'                                                      AS unit,
    '15m'                                                    AS period,
    count(ok)                                                AS rows,
    CAST(min(time) FILTER (WHERE ok IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE ok IS NOT NULL) AS VARCHAR) AS newest
FROM domain
UNION ALL
SELECT
    'domain/resolver'                                           AS relation,
    'score'                                                     AS measure,
    'int'                                                       AS kind,
    '-'                                                         AS unit,
    '15m'                                                       AS period,
    count(score)                                                AS rows,
    CAST(min(time) FILTER (WHERE score IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE score IS NOT NULL) AS VARCHAR) AS newest
FROM domain
UNION ALL
SELECT
    'domain/resolver'                                                     AS relation,
    'resolvers_total'                                                     AS measure,
    'int'                                                                 AS kind,
    '-'                                                                   AS unit,
    '15m'                                                                 AS period,
    count(resolvers_total)                                                AS rows,
    CAST(min(time) FILTER (WHERE resolvers_total IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE resolvers_total IS NOT NULL) AS VARCHAR) AS newest
FROM domain
UNION ALL
SELECT
    'domain/resolver'                                                  AS relation,
    'resolvers_ok'                                                     AS measure,
    'int'                                                              AS kind,
    '-'                                                                AS unit,
    '15m'                                                              AS period,
    count(resolvers_ok)                                                AS rows,
    CAST(min(time) FILTER (WHERE resolvers_ok IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE resolvers_ok IS NOT NULL) AS VARCHAR) AS newest
FROM domain
UNION ALL
SELECT
    'domain/resolver'                                                      AS relation,
    'resolvers_failed'                                                     AS measure,
    'int'                                                                  AS kind,
    '-'                                                                    AS unit,
    '15m'                                                                  AS period,
    count(resolvers_failed)                                                AS rows,
    CAST(min(time) FILTER (WHERE resolvers_failed IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE resolvers_failed IS NOT NULL) AS VARCHAR) AS newest
FROM domain
UNION ALL
SELECT
    '-'                   AS relation,
    column_name           AS measure,
    '-'                   AS kind,
    '-'                   AS unit,
    '-'                   AS period,
    CAST(NULL AS BIGINT)  AS rows,
    CAST(NULL AS VARCHAR) AS oldest,
    CAST(NULL AS VARCHAR) AS newest
FROM information_schema.columns
WHERE
    table_name = 'domain'
    AND column_name NOT IN ('ok', 'resolvers_failed', 'resolvers_ok', 'resolvers_total', 'score', 'time')
UNION ALL
SELECT
    'ethernet/port'                                             AS relation,
    'score'                                                     AS measure,
    'int'                                                       AS kind,
    '-'                                                         AS unit,
    '15m'                                                       AS period,
    count(score)                                                AS rows,
    CAST(min(time) FILTER (WHERE score IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE score IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
UNION ALL
SELECT
    'ethernet/port'                                          AS relation,
    'ok'                                                     AS measure,
    'bool'                                                   AS kind,
    '-'                                                      AS unit,
    '15m'                                                    AS period,
    count(ok)                                                AS rows,
    CAST(min(time) FILTER (WHERE ok IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE ok IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
UNION ALL
SELECT
    'ethernet/port'                                                   AS relation,
    'ports_total'                                                     AS measure,
    'int'                                                             AS kind,
    '-'                                                               AS unit,
    '15m'                                                             AS period,
    count(ports_total)                                                AS rows,
    CAST(min(time) FILTER (WHERE ports_total IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE ports_total IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
UNION ALL
SELECT
    'ethernet/port'                                                AS relation,
    'ports_ok'                                                     AS measure,
    'int'                                                          AS kind,
    '-'                                                            AS unit,
    '15m'                                                          AS period,
    count(ports_ok)                                                AS rows,
    CAST(min(time) FILTER (WHERE ports_ok IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE ports_ok IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
UNION ALL
SELECT
    'ethernet/port'                                                      AS relation,
    'ports_degraded'                                                     AS measure,
    'int'                                                                AS kind,
    '-'                                                                  AS unit,
    '15m'                                                                AS period,
    count(ports_degraded)                                                AS rows,
    CAST(min(time) FILTER (WHERE ports_degraded IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE ports_degraded IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
UNION ALL
SELECT
    'ethernet/port'                                                     AS relation,
    'ports_errored'                                                     AS measure,
    'int'                                                               AS kind,
    '-'                                                                 AS unit,
    '15m'                                                               AS period,
    count(ports_errored)                                                AS rows,
    CAST(min(time) FILTER (WHERE ports_errored IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE ports_errored IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
UNION ALL
SELECT
    '-'                   AS relation,
    column_name           AS measure,
    '-'                   AS kind,
    '-'                   AS unit,
    '-'                   AS period,
    CAST(NULL AS BIGINT)  AS rows,
    CAST(NULL AS VARCHAR) AS oldest,
    CAST(NULL AS VARCHAR) AS newest
FROM information_schema.columns
WHERE
    table_name = 'ethernet'
    AND column_name NOT IN ('ok', 'ports_degraded', 'ports_errored', 'ports_ok', 'ports_total', 'score', 'time')
UNION ALL
SELECT
    'internet/gateway'                                       AS relation,
    'ok'                                                     AS measure,
    'bool'                                                   AS kind,
    '-'                                                      AS unit,
    '15m'                                                    AS period,
    count(ok)                                                AS rows,
    CAST(min(time) FILTER (WHERE ok IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE ok IS NOT NULL) AS VARCHAR) AS newest
FROM internet
UNION ALL
SELECT
    'internet/gateway'                                          AS relation,
    'score'                                                     AS measure,
    'int'                                                       AS kind,
    '-'                                                         AS unit,
    '15m'                                                       AS period,
    count(score)                                                AS rows,
    CAST(min(time) FILTER (WHERE score IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE score IS NOT NULL) AS VARCHAR) AS newest
FROM internet
UNION ALL
SELECT
    'internet/gateway'                                                  AS relation,
    'targets_total'                                                     AS measure,
    'int'                                                               AS kind,
    '-'                                                                 AS unit,
    '15m'                                                               AS period,
    count(targets_total)                                                AS rows,
    CAST(min(time) FILTER (WHERE targets_total IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE targets_total IS NOT NULL) AS VARCHAR) AS newest
FROM internet
UNION ALL
SELECT
    'internet/gateway'                                               AS relation,
    'targets_ok'                                                     AS measure,
    'int'                                                            AS kind,
    '-'                                                              AS unit,
    '15m'                                                            AS period,
    count(targets_ok)                                                AS rows,
    CAST(min(time) FILTER (WHERE targets_ok IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE targets_ok IS NOT NULL) AS VARCHAR) AS newest
FROM internet
UNION ALL
SELECT
    'internet/gateway'                                                 AS relation,
    'avg_loss_pct'                                                     AS measure,
    'float'                                                            AS kind,
    '%'                                                                AS unit,
    '15m'                                                              AS period,
    count(avg_loss_pct)                                                AS rows,
    CAST(min(time) FILTER (WHERE avg_loss_pct IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE avg_loss_pct IS NOT NULL) AS VARCHAR) AS newest
FROM internet
UNION ALL
SELECT
    'internet/gateway'                                               AS relation,
    'avg_rtt_ms'                                                     AS measure,
    'float'                                                          AS kind,
    'ms'                                                             AS unit,
    '15m'                                                            AS period,
    count(avg_rtt_ms)                                                AS rows,
    CAST(min(time) FILTER (WHERE avg_rtt_ms IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE avg_rtt_ms IS NOT NULL) AS VARCHAR) AS newest
FROM internet
UNION ALL
SELECT
    'internet/gateway'                                                  AS relation,
    'avg_jitter_ms'                                                     AS measure,
    'float'                                                             AS kind,
    'ms'                                                                AS unit,
    '15m'                                                               AS period,
    count(avg_jitter_ms)                                                AS rows,
    CAST(min(time) FILTER (WHERE avg_jitter_ms IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE avg_jitter_ms IS NOT NULL) AS VARCHAR) AS newest
FROM internet
UNION ALL
SELECT
    'internet/gateway'                                               AS relation,
    'gateway_ok'                                                     AS measure,
    'bool'                                                           AS kind,
    '-'                                                              AS unit,
    '15m'                                                            AS period,
    count(gateway_ok)                                                AS rows,
    CAST(min(time) FILTER (WHERE gateway_ok IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE gateway_ok IS NOT NULL) AS VARCHAR) AS newest
FROM internet
UNION ALL
SELECT
    '-'                   AS relation,
    column_name           AS measure,
    '-'                   AS kind,
    '-'                   AS unit,
    '-'                   AS period,
    CAST(NULL AS BIGINT)  AS rows,
    CAST(NULL AS VARCHAR) AS oldest,
    CAST(NULL AS VARCHAR) AS newest
FROM information_schema.columns
WHERE
    table_name = 'internet'
    AND column_name NOT IN (
        'avg_jitter_ms', 'avg_loss_pct', 'avg_rtt_ms', 'gateway_ok', 'ok', 'score',
        'targets_ok', 'targets_total', 'time'
    )
UNION ALL
SELECT
    'weewx/console'                                          AS relation,
    'ok'                                                     AS measure,
    'bool'                                                   AS kind,
    '-'                                                      AS unit,
    '15m'                                                    AS period,
    count(ok)                                                AS rows,
    CAST(min(time) FILTER (WHERE ok IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE ok IS NOT NULL) AS VARCHAR) AS newest
FROM weewx
UNION ALL
SELECT
    'weewx/console'                                             AS relation,
    'score'                                                     AS measure,
    'int'                                                       AS kind,
    '-'                                                         AS unit,
    '15m'                                                       AS period,
    count(score)                                                AS rows,
    CAST(min(time) FILTER (WHERE score IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE score IS NOT NULL) AS VARCHAR) AS newest
FROM weewx
UNION ALL
SELECT
    '-'                   AS relation,
    column_name           AS measure,
    '-'                   AS kind,
    '-'                   AS unit,
    '-'                   AS period,
    CAST(NULL AS BIGINT)  AS rows,
    CAST(NULL AS VARCHAR) AS oldest,
    CAST(NULL AS VARCHAR) AS newest
FROM information_schema.columns
WHERE
    table_name = 'weewx'
    AND column_name NOT IN ('ok', 'score', 'time')
UNION ALL
SELECT
    'wireless/accesspoint'                                   AS relation,
    'ok'                                                     AS measure,
    'bool'                                                   AS kind,
    '-'                                                      AS unit,
    '15m'                                                    AS period,
    count(ok)                                                AS rows,
    CAST(min(time) FILTER (WHERE ok IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE ok IS NOT NULL) AS VARCHAR) AS newest
FROM wireless
UNION ALL
SELECT
    'wireless/accesspoint'                                      AS relation,
    'score'                                                     AS measure,
    'int'                                                       AS kind,
    '-'                                                         AS unit,
    '15m'                                                       AS period,
    count(score)                                                AS rows,
    CAST(min(time) FILTER (WHERE score IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE score IS NOT NULL) AS VARCHAR) AS newest
FROM wireless
UNION ALL
SELECT
    'wireless/accesspoint'                                          AS relation,
    'aps_total'                                                     AS measure,
    'int'                                                           AS kind,
    '-'                                                             AS unit,
    '15m'                                                           AS period,
    count(aps_total)                                                AS rows,
    CAST(min(time) FILTER (WHERE aps_total IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE aps_total IS NOT NULL) AS VARCHAR) AS newest
FROM wireless
UNION ALL
SELECT
    'wireless/accesspoint'                                       AS relation,
    'aps_ok'                                                     AS measure,
    'int'                                                        AS kind,
    '-'                                                          AS unit,
    '15m'                                                        AS period,
    count(aps_ok)                                                AS rows,
    CAST(min(time) FILTER (WHERE aps_ok IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE aps_ok IS NOT NULL) AS VARCHAR) AS newest
FROM wireless
UNION ALL
SELECT
    'wireless/accesspoint'                                                   AS relation,
    'avg_experience_pct'                                                     AS measure,
    'float'                                                                  AS kind,
    '%'                                                                      AS unit,
    '15m'                                                                    AS period,
    count(avg_experience_pct)                                                AS rows,
    CAST(min(time) FILTER (WHERE avg_experience_pct IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE avg_experience_pct IS NOT NULL) AS VARCHAR) AS newest
FROM wireless
UNION ALL
SELECT
    '-'                   AS relation,
    column_name           AS measure,
    '-'                   AS kind,
    '-'                   AS unit,
    '-'                   AS period,
    CAST(NULL AS BIGINT)  AS rows,
    CAST(NULL AS VARCHAR) AS oldest,
    CAST(NULL AS VARCHAR) AS newest
FROM information_schema.columns
WHERE
    table_name = 'wireless'
    AND column_name NOT IN ('aps_ok', 'aps_total', 'avg_experience_pct', 'ok', 'score', 'time')
UNION ALL
SELECT
    'zigbee/bridge'                                          AS relation,
    'ok'                                                     AS measure,
    'bool'                                                   AS kind,
    '-'                                                      AS unit,
    '15m'                                                    AS period,
    count(ok)                                                AS rows,
    CAST(min(time) FILTER (WHERE ok IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE ok IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
UNION ALL
SELECT
    'zigbee/bridge'                                             AS relation,
    'score'                                                     AS measure,
    'int'                                                       AS kind,
    '-'                                                         AS unit,
    '15m'                                                       AS period,
    count(score)                                                AS rows,
    CAST(min(time) FILTER (WHERE score IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE score IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
UNION ALL
SELECT
    'zigbee/bridge'                                                     AS relation,
    'devices_total'                                                     AS measure,
    'int'                                                               AS kind,
    '-'                                                                 AS unit,
    '15m'                                                               AS period,
    count(devices_total)                                                AS rows,
    CAST(min(time) FILTER (WHERE devices_total IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE devices_total IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
UNION ALL
SELECT
    'zigbee/bridge'                                                  AS relation,
    'devices_ok'                                                     AS measure,
    'int'                                                            AS kind,
    '-'                                                              AS unit,
    '15m'                                                            AS period,
    count(devices_ok)                                                AS rows,
    CAST(min(time) FILTER (WHERE devices_ok IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE devices_ok IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
UNION ALL
SELECT
    'zigbee/bridge'                                                    AS relation,
    'devices_weak'                                                     AS measure,
    'int'                                                              AS kind,
    '-'                                                                AS unit,
    '15m'                                                              AS period,
    count(devices_weak)                                                AS rows,
    CAST(min(time) FILTER (WHERE devices_weak IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE devices_weak IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
UNION ALL
SELECT
    'zigbee/bridge'                                               AS relation,
    'avg_lqi'                                                     AS measure,
    'float'                                                       AS kind,
    '-'                                                           AS unit,
    '15m'                                                         AS period,
    count(avg_lqi)                                                AS rows,
    CAST(min(time) FILTER (WHERE avg_lqi IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE avg_lqi IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
UNION ALL
SELECT
    '-'                   AS relation,
    column_name           AS measure,
    '-'                   AS kind,
    '-'                   AS unit,
    '-'                   AS period,
    CAST(NULL AS BIGINT)  AS rows,
    CAST(NULL AS VARCHAR) AS oldest,
    CAST(NULL AS VARCHAR) AS newest
FROM information_schema.columns
WHERE
    table_name = 'zigbee'
    AND column_name NOT IN ('avg_lqi', 'devices_ok', 'devices_total', 'devices_weak', 'ok', 'score', 'time')
ORDER BY rows DESC NULLS LAST;

-- entities
