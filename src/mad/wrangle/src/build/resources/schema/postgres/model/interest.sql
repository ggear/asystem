--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- interest/rate [interest and inflation rates published by the Reserve Bank of Australia]
--   cadence 1d
--   tag entity* [rate series]
--   entity Bank, Inflation, Net
--   field mean % 1mo [mean rate across the month]
--   field mean % 1y [mean rate across [1 Year Mean]]
--   field mean % 5y [mean rate across [5 Year Mean]]
--   field mean % 10y [mean rate across [10 Year Mean]]
--   field mean % 20y [mean rate across [20 Year Mean]]
--   field mean % 40y [mean rate across [40 Year Mean]]

CREATE TABLE IF NOT EXISTS interest (
    time   DATE   NOT NULL,
    entity TEXT   NOT NULL,
    type   TEXT   NOT NULL,
    period TEXT   NOT NULL,
    unit   TEXT   NOT NULL,
    value  FLOAT8 NOT NULL,
    PRIMARY KEY (time, entity, type, period, unit)
);

SELECT create_hypertable('interest', 'time', chunk_time_interval => INTERVAL '10 years', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS interest_entity_time ON interest (entity, time DESC);
CREATE INDEX IF NOT EXISTS interest_type_time ON interest (type, time DESC);
CREATE INDEX IF NOT EXISTS interest_period_time ON interest (period, time DESC);
CREATE INDEX IF NOT EXISTS interest_unit_time ON interest (unit, time DESC);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM timescaledb_information.compression_settings WHERE hypertable_name = 'interest') THEN
        ALTER TABLE interest SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'entity, type, period, unit',
            timescaledb.compress_orderby = 'time DESC');
        PERFORM add_compression_policy('interest', INTERVAL '1 year', if_not_exists => TRUE);
    END IF;
END $$;
