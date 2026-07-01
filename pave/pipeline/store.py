# all SQLite reads and writes live here — raw sqlite3, no ORM
# securities: INSERT OR REPLACE (idempotent re-runs)
# prices: INSERT OR IGNORE (skip duplicates, don't update existing rows)

import logging
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def init_db(db_path: Path) -> sqlite3.Connection:
    """Create the DB and apply schema DDL. Returns an open connection."""
    schema_path = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema_path.read_text())
    conn.commit()
    logger.info("Database initialised at %s", db_path)
    return conn


def upsert_securities(conn: sqlite3.Connection, universe: list[dict]) -> None:
    """Insert or replace securities. Each dict needs: ticker, name, sector."""
    rows = [(s["ticker"], s["name"], s["sector"]) for s in universe]
    conn.executemany(
        "INSERT OR REPLACE INTO securities (ticker, name, sector) VALUES (?, ?, ?)",
        rows,
    )
    conn.commit()
    logger.info("Upserted %d securities.", len(rows))


def insert_prices(conn: sqlite3.Connection, df: pd.DataFrame) -> None:
    """Insert prices. Skips existing (ticker, date) pairs silently.

    df needs: ticker, date, open, high, low, close, volume, adj_close
    """
    df = df.copy()
    df["date"] = df["date"].astype(str)

    rows = df[
        ["ticker", "date", "open", "high", "low", "close", "volume", "adj_close"]
    ].itertuples(index=False, name=None)

    cursor = conn.executemany(
        """
        INSERT OR IGNORE INTO prices
            (ticker, date, open, high, low, close, volume, adj_close)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    logger.info("Inserted %d new price rows (skipped duplicates).", cursor.rowcount)


def row_counts(conn: sqlite3.Connection) -> dict:
    """Return a summary of how many rows are in each table — useful for smoke-testing."""
    return {
        "securities": conn.execute("SELECT COUNT(*) FROM securities").fetchone()[0],
        "prices": conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0],
    }


def load_securities(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Return all rows from the securities table as a DataFrame.
    Columns: ticker (str), name (str), sector (str).
    """
    return pd.read_sql_query("SELECT ticker, name, sector FROM securities", conn)


def load_prices(
    conn: sqlite3.Connection,
    tickers: list[str],
    start: date,
    end: date,
) -> pd.DataFrame:
    """
    Return adj_close prices for the given tickers over [start, end] inclusive.
    Columns: ticker (str), date (str, YYYY-MM-DD), adj_close (float).

    Only adj_close is returned — all portfolio return calculations depend
    solely on the adjusted closing price. Raw OHLCV columns are omitted
    to keep the downstream interface minimal.
    """
    placeholders = ",".join("?" * len(tickers))
    sql = f"""
        SELECT ticker, date, adj_close
        FROM prices
        WHERE ticker IN ({placeholders})
          AND date >= ?
          AND date <= ?
        ORDER BY ticker, date
    """
    params = tickers + [start.isoformat(), end.isoformat()]
    return pd.read_sql_query(sql, conn, params=params)


def insert_lots(
    conn: sqlite3.Connection,
    lots: list[dict],
    simulation_id: str,
) -> None:
    """
    Persist all lots (open and harvested) for a simulation run.

    lot_id is assigned by SQLite AUTOINCREMENT at insert time. The in-memory
    lot_id values used during simulation are NOT stored here — the DB is the
    authoritative source of lot_id after persistence. This means sold_lot_id
    in harvest_events references the in-memory counter, not the DB id.
    See harvest_events schema comment for details.
    """
    rows = [
        (
            simulation_id,
            lot["ticker"],
            lot["purchase_date"],
            lot["quantity"],
            lot["cost_basis_per_share"],
            lot["status"],
        )
        for lot in lots
    ]
    conn.executemany(
        """
        INSERT INTO tax_lots
            (simulation_id, ticker, purchase_date, quantity, cost_basis_per_share, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    logger.info("Inserted %d tax lots for simulation %s.", len(rows), simulation_id)


def insert_harvest_events(
    conn: sqlite3.Connection,
    events: list[dict],
    simulation_id: str,
) -> None:
    """
    Persist harvest events for a simulation run. No-op if events is empty.
    """
    if not events:
        return
    rows = [
        (
            simulation_id,
            e["event_date"],
            e["sold_ticker"],
            e["sold_lot_id"],
            e["sold_quantity"],
            e["sold_price"],
            e["realized_loss"],
            e["replacement_ticker"],
            e["replacement_cost_basis"],
        )
        for e in events
    ]
    conn.executemany(
        """
        INSERT INTO harvest_events
            (simulation_id, event_date, sold_ticker, sold_lot_id,
             sold_quantity, sold_price, realized_loss,
             replacement_ticker, replacement_cost_basis)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    logger.info("Inserted %d harvest events for simulation %s.", len(rows), simulation_id)


def load_lots(conn: sqlite3.Connection, simulation_id: str) -> pd.DataFrame:
    """Return all tax lots for a simulation as a DataFrame."""
    return pd.read_sql_query(
        "SELECT * FROM tax_lots WHERE simulation_id = ? ORDER BY purchase_date, ticker",
        conn,
        params=(simulation_id,),
    )


def load_harvest_events(conn: sqlite3.Connection, simulation_id: str) -> pd.DataFrame:
    """Return all harvest events for a simulation as a DataFrame."""
    return pd.read_sql_query(
        "SELECT * FROM harvest_events WHERE simulation_id = ? ORDER BY event_date",
        conn,
        params=(simulation_id,),
    )
