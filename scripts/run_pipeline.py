"""
Entrypoint: pull prices for the full universe and persist to SQLite.

Usage:
    python scripts/run_pipeline.py

Optional env overrides (useful for testing with a smaller universe):
    PAVE_TICKERS="AAPL,MSFT,GOOG"  python scripts/run_pipeline.py
"""

import logging
import os
import sys
from pathlib import Path

# Allow running from the project root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pave.config import DB_PATH, END_DATE, START_DATE, TICKERS, UNIVERSE
from pave.pipeline.fetch import fetch_prices
from pave.pipeline.store import init_db, insert_prices, row_counts, upsert_securities
from pave.pipeline.validate import validate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_pipeline")


def main() -> None:
    # Allow overriding the ticker list via environment variable for quick tests.
    env_tickers = os.environ.get("PAVE_TICKERS")
    if env_tickers:
        tickers = [t.strip() for t in env_tickers.split(",") if t.strip()]
        universe = [s for s in UNIVERSE if s["ticker"] in set(tickers)]
        logger.info("Ticker override active: %s", tickers)
    else:
        tickers = TICKERS
        universe = UNIVERSE

    # 1. Initialise database (creates tables if they don't exist).
    conn = init_db(DB_PATH)

    # 2. Upsert securities metadata.
    upsert_securities(conn, universe)

    # 3. Fetch raw price data from yfinance.
    raw_df = fetch_prices(tickers, START_DATE, END_DATE)

    # 4. Validate and clean.
    clean_df = validate(raw_df, START_DATE, END_DATE)

    # 5. Persist to SQLite.
    insert_prices(conn, clean_df)

    # 6. Report final row counts.
    counts = row_counts(conn)
    logger.info("Pipeline complete. DB state: %s", counts)

    conn.close()


if __name__ == "__main__":
    main()
