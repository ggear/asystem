--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- an archived measure is retained deliberately with nothing to delete, silenced in verify and describe, and this reports the history it still carries
SELECT
    'zigbee'                                                          AS relation,
    'coordinator'                                                     AS measure,
    count(coordinator)                                                AS carried,
    CAST(min(time) FILTER (WHERE coordinator IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE coordinator IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
UNION ALL
SELECT
    'zigbee'                                                                AS relation,
    'coordinator_trend'                                                     AS measure,
    count(coordinator_trend)                                                AS carried,
    CAST(min(time) FILTER (WHERE coordinator_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE coordinator_trend IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
UNION ALL
SELECT
    'zigbee'                                                       AS relation,
    'degraded'                                                     AS measure,
    count(degraded)                                                AS carried,
    CAST(min(time) FILTER (WHERE degraded IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE degraded IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
UNION ALL
SELECT
    'zigbee'                                                             AS relation,
    'degraded_trend'                                                     AS measure,
    count(degraded_trend)                                                AS carried,
    CAST(min(time) FILTER (WHERE degraded_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE degraded_trend IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
UNION ALL
SELECT
    'zigbee'                                                     AS relation,
    'errors'                                                     AS measure,
    count(errors)                                                AS carried,
    CAST(min(time) FILTER (WHERE errors IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE errors IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
UNION ALL
SELECT
    'zigbee'                                                           AS relation,
    'errors_trend'                                                     AS measure,
    count(errors_trend)                                                AS carried,
    CAST(min(time) FILTER (WHERE errors_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE errors_trend IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
UNION ALL
SELECT
    'zigbee'                                                          AS relation,
    'full_duplex'                                                     AS measure,
    count(full_duplex)                                                AS carried,
    CAST(min(time) FILTER (WHERE full_duplex IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE full_duplex IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
UNION ALL
SELECT
    'zigbee'                                                                AS relation,
    'full_duplex_trend'                                                     AS measure,
    count(full_duplex_trend)                                                AS carried,
    CAST(min(time) FILTER (WHERE full_duplex_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE full_duplex_trend IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
UNION ALL
SELECT
    'zigbee'                                                   AS relation,
    'port'                                                     AS measure,
    count(port)                                                AS carried,
    CAST(min(time) FILTER (WHERE port IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE port IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
UNION ALL
SELECT
    'zigbee'                                                         AS relation,
    'port_trend'                                                     AS measure,
    count(port_trend)                                                AS carried,
    CAST(min(time) FILTER (WHERE port_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE port_trend IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
UNION ALL
SELECT
    'zigbee'                                                         AS relation,
    'speed_mbps'                                                     AS measure,
    count(speed_mbps)                                                AS carried,
    CAST(min(time) FILTER (WHERE speed_mbps IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE speed_mbps IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
UNION ALL
SELECT
    'zigbee'                                                               AS relation,
    'speed_mbps_trend'                                                     AS measure,
    count(speed_mbps_trend)                                                AS carried,
    CAST(min(time) FILTER (WHERE speed_mbps_trend IS NOT NULL) AS VARCHAR) AS oldest,
    CAST(max(time) FILTER (WHERE speed_mbps_trend IS NOT NULL) AS VARCHAR) AS newest
FROM zigbee
ORDER BY measure;
