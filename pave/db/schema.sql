-- =============================================================================
-- Schema for the Direct Indexing / Tax-Loss Harvesting simulator
-- =============================================================================

-- One row per stock in our universe.
-- sector is used for portfolio construction (sector-weighting constraints)
-- and for replacement security selection during harvesting.
CREATE TABLE IF NOT EXISTS securities (
    ticker  TEXT PRIMARY KEY,
    name    TEXT NOT NULL,
    sector  TEXT NOT NULL
);

-- One row per ticker per trading day.
-- adj_close is the split- and dividend-adjusted close from yfinance.
-- We use adj_close for all return calculations; raw OHLCV is stored for
-- completeness and potential future use.
CREATE TABLE IF NOT EXISTS prices (
    ticker      TEXT    NOT NULL,
    date        TEXT    NOT NULL,   -- ISO 8601: YYYY-MM-DD
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL,
    volume      INTEGER,
    adj_close   REAL    NOT NULL,
    PRIMARY KEY (ticker, date),
    FOREIGN KEY (ticker) REFERENCES securities(ticker)
);

-- Index to speed up time-range queries (the main access pattern in simulation).
CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date);
