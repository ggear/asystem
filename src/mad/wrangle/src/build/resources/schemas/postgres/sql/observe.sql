--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- open entity domains, printed for eyeballing and never asserted
SELECT
    'equity'  AS relation,
    entity,
    count(*)  AS rows_total,
    max(time) AS last_seen
FROM equity
GROUP BY entity
ORDER BY entity;
