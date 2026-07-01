CREATE TABLE IF NOT EXISTS securities (
    ticker  TEXT PRIMARY KEY,
    name    TEXT NOT NULL,
    sector  TEXT NOT NULL
);

-- daily prices — adj_close is what we actually use for return calculations,
-- raw OHLCV kept for completeness
CREATE TABLE IF NOT EXISTS prices (
    ticker      TEXT    NOT NULL,
    date        TEXT    NOT NULL,
    open        REAL,
    high        REAL,
    low         REAL,
    close       REAL,
    volume      INTEGER,
    adj_close   REAL    NOT NULL,
    PRIMARY KEY (ticker, date),
    FOREIGN KEY (ticker) REFERENCES securities(ticker)
);

CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date);

-- one row per buy — never deleted, acts as an audit trail
-- status is 'open' until the lot is harvested
-- simulation_id (UUID) lets us run multiple simulations without them colliding
CREATE TABLE IF NOT EXISTS tax_lots (
    lot_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    simulation_id         TEXT    NOT NULL,
    ticker                TEXT    NOT NULL,
    purchase_date         TEXT    NOT NULL,
    quantity              REAL    NOT NULL,
    cost_basis_per_share  REAL    NOT NULL,
    status                TEXT    NOT NULL
        CHECK (status IN ('open', 'harvested')),
    FOREIGN KEY (ticker) REFERENCES securities(ticker)
);

CREATE INDEX IF NOT EXISTS idx_lots_simulation ON tax_lots(simulation_id);

-- one row per harvest action
-- realized_loss is negative for an actual loss, positive for a gain
-- sold_lot_id is the in-memory counter from simulate.py, NOT the DB lot_id
-- (they diverge after batch insert — known tradeoff, would fix with INSERT...RETURNING in prod)
CREATE TABLE IF NOT EXISTS harvest_events (
    event_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    simulation_id          TEXT    NOT NULL,
    event_date             TEXT    NOT NULL,
    sold_ticker            TEXT    NOT NULL,
    sold_lot_id            INTEGER NOT NULL,
    sold_quantity          REAL    NOT NULL,
    sold_price             REAL    NOT NULL,
    realized_loss          REAL    NOT NULL,
    replacement_ticker     TEXT    NOT NULL,
    replacement_cost_basis REAL    NOT NULL,
    FOREIGN KEY (sold_ticker) REFERENCES securities(ticker)
);

CREATE INDEX IF NOT EXISTS idx_harvest_simulation ON harvest_events(simulation_id);
