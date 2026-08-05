--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- tempstat/device [the tempstat service itself, one row set per poll]
-- vocabulary, one row per declared (entity, type, period, unit)
--   entity tempstat
--   type period_ms period 15m unit milliseconds [wall time taken to sample every sensor]
--   type sensors_failed period 15m unit count [sensors that did not return a reading this poll]
--
-- tempstat/sensor [one DS18B20 probe on the one-wire bus]
-- vocabulary, one row per declared (entity, type, period, unit)
--   entity utility_temperature
--   entity rack_top_temperature
--   entity rack_bottom_temperature
--   type temperature_celsius period 15m unit celsius [probe temperature, absent when the sensor fails]

CREATE TABLE IF NOT EXISTS tempstat (
    time   TIMESTAMPTZ NOT NULL,
    entity TEXT   NOT NULL,
    type   TEXT   NOT NULL,
    period TEXT   NOT NULL,
    unit   TEXT   NOT NULL,
    value  FLOAT8 NOT NULL,
    PRIMARY KEY (time, entity, type, period, unit)
);

SELECT create_hypertable('tempstat', 'time', chunk_time_interval => INTERVAL '1 month', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS tempstat_entity_time ON tempstat (entity, time DESC);
CREATE INDEX IF NOT EXISTS tempstat_type_time ON tempstat (type, time DESC);
CREATE INDEX IF NOT EXISTS tempstat_period_time ON tempstat (period, time DESC);
CREATE INDEX IF NOT EXISTS tempstat_unit_time ON tempstat (unit, time DESC);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM timescaledb_information.compression_settings WHERE hypertable_name = 'tempstat') THEN
        ALTER TABLE tempstat SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'entity, type, period, unit',
            timescaledb.compress_orderby = 'time DESC');
        PERFORM add_compression_policy('tempstat', INTERVAL '1 year', if_not_exists => TRUE);
    END IF;
END $$;

SELECT add_retention_policy('tempstat', INTERVAL '2 years', if_not_exists => TRUE);
