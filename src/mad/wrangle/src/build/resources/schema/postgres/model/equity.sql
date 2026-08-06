--------------------------------------------------------------------------------
-- WARNING: This file is written by the build process, any manual edits will be lost!
--------------------------------------------------------------------------------

-- equity/ticker [equity prices and volumes downloaded per ticker]
--   cadence 1d
--   tag entity* [ticker symbol]
--   entity ACDC, AORD, ATOI, AXJO, BANK, CLNE, EMKT, ERTH, GAME, GOLD, IAF, MCK, MUK, MUS, MVW, NDQ, QSML,
--   entity SIG, URNM, VAE, VAS, VDHG, VGE, VGS, VHY, WDS
--   field market-volume-spot $ 1d [daily market volume spot reading]
--   field price-close $ 1d [daily price close reading]
--   field price-close-base $ 1d [daily price close base reading]
--   field price-close-spot $ 1d [daily price close spot reading]
--   field price-close-1d-change-percentage % 1d [change in price close across [1] days]
--   field price-close-base-1d-change-percentage % 1d [change in price close base across [1] days]
--   field price-close-spot-1d-change-percentage % 1d [change in price close spot across [1] days]
--   field price-close-30d-change-percentage % 30d [change in price close across [30] days]
--   field price-close-base-30d-change-percentage % 30d [change in price close base across [30] days]
--   field price-close-spot-30d-change-percentage % 30d [change in price close spot across [30] days]
--   field price-close-90d-change-percentage % 90d [change in price close across [90] days]
--   field price-close-base-90d-change-percentage % 90d [change in price close base across [90] days]
--   field price-close-spot-90d-change-percentage % 90d [change in price close spot across [90] days]
--   field price-close-365d-change-percentage % 365d [change in price close across [365] days]
--   field price-close-base-365d-change-percentage % 365d [change in price close base across [365] days]
--   field price-close-spot-365d-change-percentage % 365d [change in price close spot across [365] days]

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
