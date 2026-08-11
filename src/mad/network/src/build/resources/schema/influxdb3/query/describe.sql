--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- dimensions
SELECT
    'certificate/endpoint'     AS relation,
    'endpoint*'                AS dimension,
    3                          AS measures,
    '15m'                      AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM certificate
WHERE
    module = 'network'
    AND endpoint IS NOT NULL
UNION ALL
SELECT
    'diagnosis/plugin'         AS relation,
    'plugin*'                  AS dimension,
    2                          AS measures,
    '15m'                      AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM diagnosis
WHERE
    module = 'network'
    AND plugin IS NOT NULL
UNION ALL
SELECT
    'domain/resolver'          AS relation,
    'resolver*'                AS dimension,
    3                          AS measures,
    '15m'                      AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM domain
WHERE
    module = 'network'
    AND resolver IS NOT NULL
UNION ALL
SELECT
    'ethernet/port'            AS relation,
    'port*'                    AS dimension,
    5                          AS measures,
    '15m'                      AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND port IS NOT NULL
UNION ALL
SELECT
    'internet/target'          AS relation,
    'target*'                  AS dimension,
    4                          AS measures,
    '15m'                      AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM internet
WHERE
    module = 'network'
    AND target IS NOT NULL
UNION ALL
SELECT
    'weewx/console'            AS relation,
    'console*'                 AS dimension,
    2                          AS measures,
    '15m'                      AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM weewx
WHERE
    module = 'network'
    AND console IS NOT NULL
UNION ALL
SELECT
    'wireless/accesspoint'     AS relation,
    'accesspoint*'             AS dimension,
    3                          AS measures,
    '15m'                      AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM wireless
WHERE
    module = 'network'
    AND accesspoint IS NOT NULL
UNION ALL
SELECT
    'zigbee/device'            AS relation,
    'device*'                  AS dimension,
    4                          AS measures,
    '15m'                      AS cadence,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM zigbee
WHERE
    module = 'network'
    AND device IS NOT NULL
ORDER BY rows DESC;

-- measures
SELECT
    'certificate/endpoint'                                         AS relation,
    'verified'                                                     AS measure,
    'bool'                                                         AS kind,
    '-'                                                            AS unit,
    '15m'                                                          AS period,
    count(verified)                                                AS rows,
    CAST(min(time) FILTER (WHERE verified IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE verified IS NOT NULL) AS VARCHAR) AS newest
FROM certificate
WHERE
    module = 'network'
    AND endpoint IS NOT NULL
UNION ALL
SELECT
    'certificate/endpoint'                                            AS relation,
    'expiry_days'                                                     AS measure,
    'float'                                                           AS kind,
    'd'                                                               AS unit,
    '15m'                                                             AS period,
    count(expiry_days)                                                AS rows,
    CAST(min(time) FILTER (WHERE expiry_days IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE expiry_days IS NOT NULL) AS VARCHAR) AS newest
FROM certificate
WHERE
    module = 'network'
    AND endpoint IS NOT NULL
UNION ALL
SELECT
    'certificate/endpoint'                                             AS relation,
    'validity_pct'                                                     AS measure,
    'float'                                                            AS kind,
    '%'                                                                AS unit,
    '15m'                                                              AS period,
    count(validity_pct)                                                AS rows,
    CAST(min(time) FILTER (WHERE validity_pct IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE validity_pct IS NOT NULL) AS VARCHAR) AS newest
FROM certificate
WHERE
    module = 'network'
    AND endpoint IS NOT NULL
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
    AND column_name NOT IN ('endpoint', 'expiry_days', 'module', 'time', 'validity_pct', 'verified')
UNION ALL
SELECT
    'diagnosis/plugin'                                       AS relation,
    'ok'                                                     AS measure,
    'bool'                                                   AS kind,
    '-'                                                      AS unit,
    '15m'                                                    AS period,
    count(ok)                                                AS rows,
    CAST(min(time) FILTER (WHERE ok IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE ok IS NOT NULL) AS VARCHAR) AS newest
FROM diagnosis
WHERE
    module = 'network'
    AND plugin IS NOT NULL
UNION ALL
SELECT
    'diagnosis/plugin'                                          AS relation,
    'score'                                                     AS measure,
    'int'                                                       AS kind,
    '-'                                                         AS unit,
    '15m'                                                       AS period,
    count(score)                                                AS rows,
    CAST(min(time) FILTER (WHERE score IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE score IS NOT NULL) AS VARCHAR) AS newest
FROM diagnosis
WHERE
    module = 'network'
    AND plugin IS NOT NULL
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
    table_name = 'diagnosis'
    AND column_name NOT IN ('module', 'ok', 'plugin', 'score', 'time')
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
WHERE
    module = 'network'
    AND resolver IS NOT NULL
UNION ALL
SELECT
    'domain/resolver'                                              AS relation,
    'resolved'                                                     AS measure,
    'bool'                                                         AS kind,
    '-'                                                            AS unit,
    '15m'                                                          AS period,
    count(resolved)                                                AS rows,
    CAST(min(time) FILTER (WHERE resolved IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE resolved IS NOT NULL) AS VARCHAR) AS newest
FROM domain
WHERE
    module = 'network'
    AND resolver IS NOT NULL
UNION ALL
SELECT
    'domain/resolver'                                                AS relation,
    'latency_ms'                                                     AS measure,
    'float'                                                          AS kind,
    'ms'                                                             AS unit,
    '15m'                                                            AS period,
    count(latency_ms)                                                AS rows,
    CAST(min(time) FILTER (WHERE latency_ms IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE latency_ms IS NOT NULL) AS VARCHAR) AS newest
FROM domain
WHERE
    module = 'network'
    AND resolver IS NOT NULL
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
    AND column_name NOT IN ('latency_ms', 'module', 'ok', 'resolved', 'resolver', 'time')
UNION ALL
SELECT
    'ethernet/port'                                          AS relation,
    'up'                                                     AS measure,
    'bool'                                                   AS kind,
    '-'                                                      AS unit,
    '15m'                                                    AS period,
    count(up)                                                AS rows,
    CAST(min(time) FILTER (WHERE up IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE up IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND port IS NOT NULL
UNION ALL
SELECT
    'ethernet/port'                                                  AS relation,
    'speed_mbps'                                                     AS measure,
    'int'                                                            AS kind,
    'Mbps'                                                           AS unit,
    '15m'                                                            AS period,
    count(speed_mbps)                                                AS rows,
    CAST(min(time) FILTER (WHERE speed_mbps IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE speed_mbps IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND port IS NOT NULL
UNION ALL
SELECT
    'ethernet/port'                                                   AS relation,
    'full_duplex'                                                     AS measure,
    'bool'                                                            AS kind,
    '-'                                                               AS unit,
    '15m'                                                             AS period,
    count(full_duplex)                                                AS rows,
    CAST(min(time) FILTER (WHERE full_duplex IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE full_duplex IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND port IS NOT NULL
UNION ALL
SELECT
    'ethernet/port'                                                AS relation,
    'degraded'                                                     AS measure,
    'bool'                                                         AS kind,
    '-'                                                            AS unit,
    '15m'                                                          AS period,
    count(degraded)                                                AS rows,
    CAST(min(time) FILTER (WHERE degraded IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE degraded IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND port IS NOT NULL
UNION ALL
SELECT
    'ethernet/port'                                              AS relation,
    'errors'                                                     AS measure,
    'int'                                                        AS kind,
    '-'                                                          AS unit,
    '15m'                                                        AS period,
    count(errors)                                                AS rows,
    CAST(min(time) FILTER (WHERE errors IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE errors IS NOT NULL) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND port IS NOT NULL
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
    AND column_name NOT IN ('degraded', 'errors', 'full_duplex', 'module', 'port', 'speed_mbps', 'time', 'up')
UNION ALL
SELECT
    'internet/target'                                               AS relation,
    'reachable'                                                     AS measure,
    'bool'                                                          AS kind,
    '-'                                                             AS unit,
    '15m'                                                           AS period,
    count(reachable)                                                AS rows,
    CAST(min(time) FILTER (WHERE reachable IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE reachable IS NOT NULL) AS VARCHAR) AS newest
FROM internet
WHERE
    module = 'network'
    AND target IS NOT NULL
UNION ALL
SELECT
    'internet/target'                                              AS relation,
    'loss_pct'                                                     AS measure,
    'float'                                                        AS kind,
    '%'                                                            AS unit,
    '15m'                                                          AS period,
    count(loss_pct)                                                AS rows,
    CAST(min(time) FILTER (WHERE loss_pct IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE loss_pct IS NOT NULL) AS VARCHAR) AS newest
FROM internet
WHERE
    module = 'network'
    AND target IS NOT NULL
UNION ALL
SELECT
    'internet/target'                                            AS relation,
    'rtt_ms'                                                     AS measure,
    'float'                                                      AS kind,
    'ms'                                                         AS unit,
    '15m'                                                        AS period,
    count(rtt_ms)                                                AS rows,
    CAST(min(time) FILTER (WHERE rtt_ms IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE rtt_ms IS NOT NULL) AS VARCHAR) AS newest
FROM internet
WHERE
    module = 'network'
    AND target IS NOT NULL
UNION ALL
SELECT
    'internet/target'                                               AS relation,
    'jitter_ms'                                                     AS measure,
    'float'                                                         AS kind,
    'ms'                                                            AS unit,
    '15m'                                                           AS period,
    count(jitter_ms)                                                AS rows,
    CAST(min(time) FILTER (WHERE jitter_ms IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE jitter_ms IS NOT NULL) AS VARCHAR) AS newest
FROM internet
WHERE
    module = 'network'
    AND target IS NOT NULL
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
    AND column_name NOT IN ('jitter_ms', 'loss_pct', 'module', 'reachable', 'rtt_ms', 'target', 'time')
UNION ALL
SELECT
    'weewx/console'                                             AS relation,
    'fresh'                                                     AS measure,
    'bool'                                                      AS kind,
    '-'                                                         AS unit,
    '15m'                                                       AS period,
    count(fresh)                                                AS rows,
    CAST(min(time) FILTER (WHERE fresh IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE fresh IS NOT NULL) AS VARCHAR) AS newest
FROM weewx
WHERE
    module = 'network'
    AND console IS NOT NULL
UNION ALL
SELECT
    'weewx/console'                                                   AS relation,
    'quality_pct'                                                     AS measure,
    'float'                                                           AS kind,
    '%'                                                               AS unit,
    '15m'                                                             AS period,
    count(quality_pct)                                                AS rows,
    CAST(min(time) FILTER (WHERE quality_pct IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE quality_pct IS NOT NULL) AS VARCHAR) AS newest
FROM weewx
WHERE
    module = 'network'
    AND console IS NOT NULL
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
    AND column_name NOT IN ('console', 'fresh', 'module', 'quality_pct', 'time')
UNION ALL
SELECT
    'wireless/accesspoint'                                   AS relation,
    'up'                                                     AS measure,
    'bool'                                                   AS kind,
    '-'                                                      AS unit,
    '15m'                                                    AS period,
    count(up)                                                AS rows,
    CAST(min(time) FILTER (WHERE up IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE up IS NOT NULL) AS VARCHAR) AS newest
FROM wireless
WHERE
    module = 'network'
    AND accesspoint IS NOT NULL
UNION ALL
SELECT
    'wireless/accesspoint'                                               AS relation,
    'experience_pct'                                                     AS measure,
    'float'                                                              AS kind,
    '%'                                                                  AS unit,
    '15m'                                                                AS period,
    count(experience_pct)                                                AS rows,
    CAST(min(time) FILTER (WHERE experience_pct IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE experience_pct IS NOT NULL) AS VARCHAR) AS newest
FROM wireless
WHERE
    module = 'network'
    AND accesspoint IS NOT NULL
UNION ALL
SELECT
    'wireless/accesspoint'                                        AS relation,
    'clients'                                                     AS measure,
    'int'                                                         AS kind,
    '-'                                                           AS unit,
    '15m'                                                         AS period,
    count(clients)                                                AS rows,
    CAST(min(time) FILTER (WHERE clients IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE clients IS NOT NULL) AS VARCHAR) AS newest
FROM wireless
WHERE
    module = 'network'
    AND accesspoint IS NOT NULL
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
    AND column_name NOT IN ('accesspoint', 'clients', 'experience_pct', 'module', 'time', 'up')
UNION ALL
SELECT
    'zigbee/device'                                                 AS relation,
    'available'                                                     AS measure,
    'bool'                                                          AS kind,
    '-'                                                             AS unit,
    '15m'                                                           AS period,
    count(available)                                                AS rows,
    CAST(min(time) FILTER (WHERE available IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE available IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
WHERE
    module = 'network'
    AND device IS NOT NULL
UNION ALL
SELECT
    'zigbee/device'                                                   AS relation,
    'coordinator'                                                     AS measure,
    'bool'                                                            AS kind,
    '-'                                                               AS unit,
    '15m'                                                             AS period,
    count(coordinator)                                                AS rows,
    CAST(min(time) FILTER (WHERE coordinator IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE coordinator IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
WHERE
    module = 'network'
    AND device IS NOT NULL
UNION ALL
SELECT
    'zigbee/device'                                           AS relation,
    'lqi'                                                     AS measure,
    'int'                                                     AS kind,
    '-'                                                       AS unit,
    '15m'                                                     AS period,
    count(lqi)                                                AS rows,
    CAST(min(time) FILTER (WHERE lqi IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE lqi IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
WHERE
    module = 'network'
    AND device IS NOT NULL
UNION ALL
SELECT
    'zigbee/device'                                            AS relation,
    'weak'                                                     AS measure,
    'bool'                                                     AS kind,
    '-'                                                        AS unit,
    '15m'                                                      AS period,
    count(weak)                                                AS rows,
    CAST(min(time) FILTER (WHERE weak IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE weak IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
WHERE
    module = 'network'
    AND device IS NOT NULL
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
    AND column_name NOT IN ('available', 'coordinator', 'device', 'lqi', 'module', 'time', 'weak')
ORDER BY rows DESC NULLS LAST;

-- entities
SELECT
    'certificate/endpoint'                                                        AS relation,
    'endpoint*'                                                                   AS dimension,
    endpoint                                                                      AS entity,
    CASE WHEN endpoint IN ('home.janeandgraham.com:443') THEN 'yes' ELSE 'no' END AS declared,
    count(*)                                                                      AS rows,
    CAST(min(time) AS VARCHAR)                                                    AS oldest,
    CAST(max(time) AS VARCHAR)                                                    AS newest
FROM certificate
WHERE
    module = 'network'
    AND endpoint IS NOT NULL
GROUP BY endpoint, CASE WHEN endpoint IN ('home.janeandgraham.com:443') THEN 'yes' ELSE 'no' END
UNION ALL
SELECT
    'diagnosis/plugin'                                                                                                            AS relation,
    'plugin*'                                                                                                                     AS dimension,
    plugin                                                                                                                        AS entity,
    CASE WHEN plugin IN ('certificate', 'domain', 'ethernet', 'internet', 'weewx', 'wireless', 'zigbee') THEN 'yes' ELSE 'no' END AS declared,
    count(*)                                                                                                                      AS rows,
    CAST(min(time) AS VARCHAR)                                                                                                    AS oldest,
    CAST(max(time) AS VARCHAR)                                                                                                    AS newest
FROM diagnosis
WHERE
    module = 'network'
    AND plugin IS NOT NULL
GROUP BY plugin, CASE WHEN plugin IN ('certificate', 'domain', 'ethernet', 'internet', 'weewx', 'wireless', 'zigbee') THEN 'yes' ELSE 'no' END
UNION ALL
SELECT
    'domain/resolver'                                                                                      AS relation,
    'resolver*'                                                                                            AS dimension,
    resolver                                                                                               AS entity,
    CASE WHEN resolver IN ('cloudflare', 'google', 'quad9', 'opendns', 'adguard') THEN 'yes' ELSE 'no' END AS declared,
    count(*)                                                                                               AS rows,
    CAST(min(time) AS VARCHAR)                                                                             AS oldest,
    CAST(max(time) AS VARCHAR)                                                                             AS newest
FROM domain
WHERE
    module = 'network'
    AND resolver IS NOT NULL
GROUP BY resolver, CASE WHEN resolver IN ('cloudflare', 'google', 'quad9', 'opendns', 'adguard') THEN 'yes' ELSE 'no' END
UNION ALL
SELECT
    'ethernet/port'            AS relation,
    'port*'                    AS dimension,
    port                       AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM ethernet
WHERE
    module = 'network'
    AND port IS NOT NULL
GROUP BY port
UNION ALL
SELECT
    'internet/target'                                                                         AS relation,
    'target*'                                                                                 AS dimension,
    target                                                                                    AS entity,
    CASE WHEN target IN ('gateway', '1.1.1.1', '8.8.8.8', '9.9.9.9') THEN 'yes' ELSE 'no' END AS declared,
    count(*)                                                                                  AS rows,
    CAST(min(time) AS VARCHAR)                                                                AS oldest,
    CAST(max(time) AS VARCHAR)                                                                AS newest
FROM internet
WHERE
    module = 'network'
    AND target IS NOT NULL
GROUP BY target, CASE WHEN target IN ('gateway', '1.1.1.1', '8.8.8.8', '9.9.9.9') THEN 'yes' ELSE 'no' END
UNION ALL
SELECT
    'weewx/console'                                                  AS relation,
    'console*'                                                       AS dimension,
    console                                                          AS entity,
    CASE WHEN console IN ('weatherstation') THEN 'yes' ELSE 'no' END AS declared,
    count(*)                                                         AS rows,
    CAST(min(time) AS VARCHAR)                                       AS oldest,
    CAST(max(time) AS VARCHAR)                                       AS newest
FROM weewx
WHERE
    module = 'network'
    AND console IS NOT NULL
GROUP BY console, CASE WHEN console IN ('weatherstation') THEN 'yes' ELSE 'no' END
UNION ALL
SELECT
    'wireless/accesspoint'     AS relation,
    'accesspoint*'             AS dimension,
    accesspoint                AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM wireless
WHERE
    module = 'network'
    AND accesspoint IS NOT NULL
GROUP BY accesspoint
UNION ALL
SELECT
    'zigbee/device'            AS relation,
    'device*'                  AS dimension,
    device                     AS entity,
    '-'                        AS declared,
    count(*)                   AS rows,
    CAST(min(time) AS VARCHAR) AS oldest,
    CAST(max(time) AS VARCHAR) AS newest
FROM zigbee
WHERE
    module = 'network'
    AND device IS NOT NULL
GROUP BY device
ORDER BY rows DESC;
