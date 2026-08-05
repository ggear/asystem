--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- equity/ticker [equity prices and volumes downloaded per ticker]
-- vocabulary, one row per declared (entity, type, period, unit)
--   entity <open domain, owned by a live third party source>
--   type market-volume-spot period 1d unit $ [daily market volume spot reading]
--   type price-close period 1d unit $ [daily price close reading]
--   type price-close-base period 1d unit $ [daily price close base reading]
--   type price-close-spot period 1d unit $ [daily price close spot reading]
--   type price-close-1d-change-percentage period 1d unit % [change in price close across [1] days]
--   type price-close-base-1d-change-percentage period 1d unit % [change in price close base across [1] days]
--   type price-close-spot-1d-change-percentage period 1d unit % [change in price close spot across [1] days]
--   type price-close-30d-change-percentage period 30d unit % [change in price close across [30] days]
--   type price-close-base-30d-change-percentage period 30d unit % [change in price close base across [30] days]
--   type price-close-spot-30d-change-percentage period 30d unit % [change in price close spot across [30] days]
--   type price-close-90d-change-percentage period 90d unit % [change in price close across [90] days]
--   type price-close-base-90d-change-percentage period 90d unit % [change in price close base across [90] days]
--   type price-close-spot-90d-change-percentage period 90d unit % [change in price close spot across [90] days]
--   type price-close-365d-change-percentage period 365d unit % [change in price close across [365] days]
--   type price-close-base-365d-change-percentage period 365d unit % [change in price close base across [365] days]
--   type price-close-spot-365d-change-percentage period 365d unit % [change in price close spot across [365] days]

CREATE TABLE IF NOT EXISTS equity (
    time   DATE   NOT NULL,
    entity TEXT   NOT NULL,
    type   TEXT   NOT NULL,
    period TEXT   NOT NULL,
    unit   TEXT   NOT NULL,
    value  FLOAT8 NOT NULL,
    PRIMARY KEY (time, entity, type, period, unit)
);

SELECT create_hypertable('equity', 'time', chunk_time_interval => INTERVAL '10 years', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS equity_entity_time ON equity (entity, time DESC);
CREATE INDEX IF NOT EXISTS equity_type_time ON equity (type, time DESC);
CREATE INDEX IF NOT EXISTS equity_period_time ON equity (period, time DESC);
CREATE INDEX IF NOT EXISTS equity_unit_time ON equity (unit, time DESC);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM timescaledb_information.compression_settings WHERE hypertable_name = 'equity') THEN
        ALTER TABLE equity SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'entity, type, period, unit',
            timescaledb.compress_orderby = 'time DESC');
        PERFORM add_compression_policy('equity', INTERVAL '1 year', if_not_exists => TRUE);
    END IF;
END $$;
