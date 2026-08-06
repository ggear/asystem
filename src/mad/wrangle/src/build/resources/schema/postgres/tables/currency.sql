--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- currency/rate [foreign exchange rates published by the Reserve Bank of Australia]
-- vocabulary, one row per declared (entity, type, period, unit)
--   entity AUD/USD
--   entity AUD/GBP
--   entity AUD/SGD
--   type snapshot period 1d unit $ [closing rate for the currency pair]
--   type delta period 1d unit % [change in the rate across [1 Day Delta]]
--   type delta period 7d unit % [change in the rate across [1 Week Delta]]
--   type delta period 30d unit % [change in the rate across [1 Month Delta]]
--   type delta period 365d unit % [change in the rate across [1 Year Delta]]

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
