"""
Tests for the data pipeline — fetch reshaping, validation logic, and store helpers.

We do NOT make live network calls here. fetch.py is tested via the _reshape
helper using synthetic DataFrames that mimic yfinance's actual output shape.
"""

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pave.pipeline.validate import validate
from pave.pipeline.store import init_db, insert_prices, upsert_securities, row_counts
from pave.pipeline.fetch import _reshape


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_price_df(ticker="AAPL", n_days=10, start=date(2024, 1, 2)) -> pd.DataFrame:
    """Build a minimal valid price DataFrame."""
    dates = [start + timedelta(days=i) for i in range(n_days)]
    return pd.DataFrame({
        "ticker": ticker,
        "date": dates,
        "open":      [150.0 + i for i in range(n_days)],
        "high":      [155.0 + i for i in range(n_days)],
        "low":       [148.0 + i for i in range(n_days)],
        "close":     [152.0 + i for i in range(n_days)],
        "volume":    [1_000_000] * n_days,
        "adj_close": [152.0 + i for i in range(n_days)],
    })


# ---------------------------------------------------------------------------
# validate() tests
# ---------------------------------------------------------------------------

class TestValidate:
    def test_passes_clean_data(self):
        df = _make_price_df()
        result = validate(df, date(2024, 1, 1), date(2024, 1, 31))
        assert len(result) == 10

    def test_drops_zero_adj_close(self):
        df = _make_price_df(n_days=5)
        df.loc[2, "adj_close"] = 0.0
        result = validate(df, date(2024, 1, 1), date(2024, 1, 31))
        assert len(result) == 4

    def test_drops_negative_adj_close(self):
        df = _make_price_df(n_days=5)
        df.loc[1, "adj_close"] = -10.0
        result = validate(df, date(2024, 1, 1), date(2024, 1, 31))
        assert len(result) == 4

    def test_drops_null_adj_close(self):
        df = _make_price_df(n_days=5)
        df.loc[0, "adj_close"] = np.nan
        result = validate(df, date(2024, 1, 1), date(2024, 1, 31))
        assert len(result) == 4

    def test_drops_duplicate_ticker_date(self):
        df = _make_price_df(n_days=5)
        df = pd.concat([df, df.iloc[[0]]], ignore_index=True)  # add duplicate row
        assert len(df) == 6
        result = validate(df, date(2024, 1, 1), date(2024, 1, 31))
        assert len(result) == 5

    def test_raises_on_missing_columns(self):
        df = _make_price_df().drop(columns=["adj_close"])
        with pytest.raises(ValueError, match="missing required columns"):
            validate(df, date(2024, 1, 1), date(2024, 1, 31))

    def test_low_coverage_does_not_raise(self, caplog):
        """Sparse data should warn but not crash — the decision to drop is left to operators."""
        import logging
        df = _make_price_df(n_days=3)   # very few rows
        with caplog.at_level(logging.WARNING):
            result = validate(df, date(2024, 1, 1), date(2024, 12, 31))
        assert len(result) == 3
        assert any("missing" in msg.lower() for msg in caplog.messages)


# ---------------------------------------------------------------------------
# store.py tests
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_conn(tmp_path):
    """Spin up a fresh in-memory-backed SQLite DB in a temp directory."""
    db_path = tmp_path / "test.db"
    conn = init_db(db_path)
    yield conn
    conn.close()


class TestStore:
    def test_init_creates_tables(self, tmp_conn):
        tables = tmp_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {t[0] for t in tables}
        assert "securities" in names
        assert "prices" in names

    def test_upsert_securities(self, tmp_conn):
        universe = [
            {"ticker": "AAPL", "name": "Apple", "sector": "Tech"},
            {"ticker": "MSFT", "name": "Microsoft", "sector": "Tech"},
        ]
        upsert_securities(tmp_conn, universe)
        count = tmp_conn.execute("SELECT COUNT(*) FROM securities").fetchone()[0]
        assert count == 2

    def test_upsert_securities_is_idempotent(self, tmp_conn):
        universe = [{"ticker": "AAPL", "name": "Apple", "sector": "Tech"}]
        upsert_securities(tmp_conn, universe)
        upsert_securities(tmp_conn, universe)  # second call should not duplicate
        count = tmp_conn.execute("SELECT COUNT(*) FROM securities").fetchone()[0]
        assert count == 1

    def test_insert_prices(self, tmp_conn):
        upsert_securities(tmp_conn, [{"ticker": "AAPL", "name": "Apple", "sector": "Tech"}])
        df = _make_price_df(ticker="AAPL", n_days=5)
        insert_prices(tmp_conn, df)
        count = tmp_conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        assert count == 5

    def test_insert_prices_ignores_duplicates(self, tmp_conn):
        upsert_securities(tmp_conn, [{"ticker": "AAPL", "name": "Apple", "sector": "Tech"}])
        df = _make_price_df(ticker="AAPL", n_days=5)
        insert_prices(tmp_conn, df)
        insert_prices(tmp_conn, df)  # re-inserting same data should be a no-op
        count = tmp_conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        assert count == 5

    def test_row_counts(self, tmp_conn):
        upsert_securities(tmp_conn, [{"ticker": "AAPL", "name": "Apple", "sector": "Tech"}])
        df = _make_price_df(ticker="AAPL", n_days=3)
        insert_prices(tmp_conn, df)
        counts = row_counts(tmp_conn)
        assert counts == {"securities": 1, "prices": 3}


# ---------------------------------------------------------------------------
# fetch._reshape tests  (no network — uses synthetic DataFrames)
# ---------------------------------------------------------------------------

class TestReshape:
    def _make_yf_multi(self, tickers, n_days=5):
        """
        Build a synthetic MultiIndex DataFrame mimicking yfinance output
        for multiple tickers (group_by='ticker').
        """
        dates = pd.date_range("2024-01-02", periods=n_days, freq="B")
        cols = pd.MultiIndex.from_product(
            [tickers, ["Open", "High", "Low", "Close", "Volume"]],
            names=["ticker", "field"],
        )
        data = np.random.uniform(100, 200, size=(n_days, len(cols)))
        df = pd.DataFrame(data, index=dates, columns=cols)
        df.index.name = "Date"
        return df

    def test_multi_ticker_shape(self):
        tickers = ["AAPL", "MSFT"]
        raw = self._make_yf_multi(tickers, n_days=5)
        result = _reshape(raw, tickers)
        assert set(result.columns) == {
            "ticker", "date", "open", "high", "low", "close", "volume", "adj_close"
        }
        assert len(result) == 10  # 2 tickers * 5 days

    def test_multi_ticker_adj_close_equals_close(self):
        tickers = ["AAPL", "MSFT"]
        raw = self._make_yf_multi(tickers, n_days=3)
        result = _reshape(raw, tickers)
        assert (result["adj_close"] == result["close"]).all()

    def test_missing_ticker_skipped(self, caplog):
        import logging
        tickers = ["AAPL", "FAKE"]
        raw = self._make_yf_multi(["AAPL"], n_days=3)
        with caplog.at_level(logging.WARNING):
            result = _reshape(raw, tickers)
        assert set(result["ticker"]) == {"AAPL"}
        assert any("FAKE" in msg for msg in caplog.messages)
