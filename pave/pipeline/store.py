"""
Read and write securities metadata and price data to SQLite.

Design notes:
- We use sqlite3 directly (no ORM) — the schema is simple and explicit,
  consistent with the raw-SQL-first approach used in the ETL background.
- Securities are upserted (INSERT OR REPLACE) so re-runs are idempotent.
- Prices are inserted with INSERT OR IGNORE so partial re-runs don't
  duplicate existing rows; if you need to update prices, delete and re-insert.
- We commit in a single transaction per call for atomicity.
- Read functions (load_*) are co-located here rather than in a separate
  reader module — the DB interface is small enough to keep in one place.
"""

import logging
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def init_db(db_path: Path) -> sqlite3.Connection:
    """
    Create the database and run the schema DDL if tables don't exist yet.
    Returns an open connection.
    """
    schema_path = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema_path.read_text())
    conn.commit()
    logger.info("Database initialised at %s", db_path)
    return conn


def upsert_securities(conn: sqlite3.Connection, universe: list[dict]) -> None:
    """
    Insert or replace securities metadata rows.
    Each dict must have keys: ticker, name, sector.
    """
    rows = [(s["ticker"], s["name"], s["sector"]) for s in universe]
    conn.executemany(
        "INSERT OR REPLACE INTO securities (ticker, name, sector) VALUES (?, ?, ?)",
        rows,
    )
    conn.commit()
    logger.info("Upserted %d securities.", len(rows))


def insert_prices(conn: sqlite3.Connection, df: pd.DataFrame) -> None:
    """
    Insert price rows. Skips rows where (ticker, date) already exists.

    df must have columns:
        ticker, date, open, high, low, close, volume, adj_close
    date values must be Python date objects or ISO strings (YYYY-MM-DD).
    """
    # Normalise date to ISO string for SQLite storage.
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
