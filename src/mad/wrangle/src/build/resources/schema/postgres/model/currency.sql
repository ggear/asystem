--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- currency/rate [foreign exchange rates published by the Reserve Bank of Australia]
--   cadence 1d
--   tag entity* [currency pair:
--     AUD/USD,
--     AUD/GBP,
--     AUD/SGD]
--   field snapshot $ 1d [closing rate for the currency pair]
--   field delta % 1d [change in the rate across [1 Day Delta]]
--   field delta % 7d [change in the rate across [1 Week Delta]]
--   field delta % 30d [change in the rate across [1 Month Delta]]
--   field delta % 365d [change in the rate across [1 Year Delta]]

CREATE TABLE IF NOT EXISTS currency (
    time   DATE   NOT NULL,
    entity TEXT   NOT NULL,
    type   TEXT   NOT NULL,
    period TEXT   NOT NULL,
    unit   TEXT   NOT NULL,
    value  FLOAT8 NOT NULL,
    PRIMARY KEY (time, entity, type, period, unit)
);

SELECT create_hypertable('currency', 'time', chunk_time_interval => INTERVAL '10 years', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS currency_entity_time ON currency (entity, time DESC);
CREATE INDEX IF NOT EXISTS currency_type_time ON currency (type, time DESC);
CREATE INDEX IF NOT EXISTS currency_period_time ON currency (period, time DESC);
CREATE INDEX IF NOT EXISTS currency_unit_time ON currency (unit, time DESC);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM timescaledb_information.compression_settings WHERE hypertable_name = 'currency') THEN
        ALTER TABLE currency SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'entity, type, period, unit',
            timescaledb.compress_orderby = 'time DESC');
        PERFORM add_compression_policy('currency', INTERVAL '1 year', if_not_exists => TRUE);
    END IF;
END $$;
