SHOW
TABLES;

SHOW
COLUMNS FROM supervisor;

SELECT DISTINCT host
FROM supervisor;

SELECT COUNT(used_processor)
FROM supervisor;

SELECT DISTINCT
ON (host) host, time, used_processor_trend
FROM supervisor
ORDER BY host, time DESC;

SELECT DISTINCT
ON (host) host, time + INTERVAL '8 hours' AS time, used_processor, used_processor_trend
FROM supervisor
ORDER BY host, time DESC;

SELECT time + INTERVAL '8 hours' AS time, host, used_processor, used_processor_trend
FROM supervisor
WHERE time >= CURRENT_TIMESTAMP - INTERVAL '10 seconds'
ORDER BY time DESC;

SELECT DATE_TRUNC('day', time + INTERVAL '8 hours') AS bin,
       host                                         AS host,
       AVG(used_processor)                          AS used_processor,
       AVG(used_processor_trend)                    AS used_processor_trend
FROM supervisor
GROUP BY bin, host
ORDER BY bin DESC;