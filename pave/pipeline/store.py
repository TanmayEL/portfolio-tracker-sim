"""
Persist securities metadata and price data to SQLite.

Design notes:
- We use sqlite3 directly (no ORM) — the schema is simple and explicit,
  consistent with the raw-SQL-first approach used in the ETL background.
- Securities are upserted (INSERT OR REPLACE) so re-runs are idempotent.
- Prices are inserted with INSERT OR IGNORE so partial re-runs don't
  duplicate existing rows; if you need to update prices, delete and re-insert.
- We commit in a single transaction per call for atomicity.
"""

import logging
import sqlite3
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
