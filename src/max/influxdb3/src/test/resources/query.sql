SHOW
TABLES;

SHOW
COLUMNS FROM cpu;

SELECT DISTINCT host
FROM cpu;

SELECT COUNT(usage_system)
FROM cpu;

SELECT DISTINCT
ON (host) host, time, usage_user
FROM cpu
ORDER BY host, time DESC;

SELECT DISTINCT
ON (host) host, time + INTERVAL '8 hours' AS time, usage_system, usage_user
FROM cpu
ORDER BY host, time DESC;

SELECT time + INTERVAL '8 hours' AS time, host, usage_system, usage_user
FROM cpu
WHERE time >= CURRENT_TIMESTAMP - INTERVAL '10 seconds'
ORDER BY time DESC;

SELECT DATE_TRUNC('day', time + INTERVAL '8 hours') AS bin,
       host                                         AS host,
       AVG(usage_system)                            AS usage_system,
       AVG(usage_user)                              AS usage_user
FROM cpu
GROUP BY bin, host
ORDER BY bin DESC;