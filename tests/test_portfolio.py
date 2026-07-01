"""
Tests for portfolio construction: benchmark weights and basket construction.

All tests use synthetic data — no database or network required.
The tmp_conn fixture spins up a fresh SQLite DB for the load_* function tests.
"""

from datetime import date, timedelta

import pandas as pd
import pytest

from pave.portfolio.benchmark import compute_benchmark_weights
from pave.portfolio.construct import construct_basket
from pave.pipeline.store import init_db, insert_prices, load_prices, load_securities, upsert_securities


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_securities(n_sectors: int = 3, stocks_per_sector: int = 4) -> pd.DataFrame:
    """Build a minimal synthetic securities DataFrame with no DB dependency."""
    rows = [
        {"ticker": f"S{s}{i}", "name": f"Stock {s}{i}", "sector": f"Sector{s}"}
        for s in range(n_sectors)
        for i in range(stocks_per_sector)
    ]
    return pd.DataFrame(rows)


def _make_price_rows(ticker: str, n_days: int = 5, start=date(2024, 1, 2)) -> pd.DataFrame:
    dates = [start + timedelta(days=i) for i in range(n_days)]
    return pd.DataFrame({
        "ticker": ticker,
        "date": dates,
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": 102.0,
        "volume": 1_000_000,
        "adj_close": 102.0,
    })


@pytest.fixture
def tmp_conn(tmp_path):
    db_path = tmp_path / "test.db"
    conn = init_db(db_path)
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# TestBenchmarkWeights
# ---------------------------------------------------------------------------

class TestBenchmarkWeights:
    def test_weights_sum_to_1(self):
        sec = _make_securities(n_sectors=3, stocks_per_sector=4)
        weights = compute_benchmark_weights(sec)
        assert abs(weights.sum() - 1.0) < 1e-9

    def test_all_sectors_have_equal_total_weight(self):
        sec = _make_securities(n_sectors=4, stocks_per_sector=3)
        weights = compute_benchmark_weights(sec)
        sector_of = sec.set_index("ticker")["sector"]
        sector_totals = weights.groupby(sector_of).sum()
        assert sector_totals.nunique() == 1  # all sector totals identical

    def test_stocks_within_sector_have_equal_weight(self):
        sec = _make_securities(n_sectors=2, stocks_per_sector=5)
        weights = compute_benchmark_weights(sec)
        # All tickers in Sector0 should share the same weight
        sector0_tickers = sec.loc[sec["sector"] == "Sector0", "ticker"]
        sector0_weights = weights[sector0_tickers]
        assert sector0_weights.nunique() == 1

    def test_single_sector_all_weight(self):
        sec = _make_securities(n_sectors=1, stocks_per_sector=4)
        weights = compute_benchmark_weights(sec)
        assert abs(weights.sum() - 1.0) < 1e-9
        # Each stock gets 1/4
        assert all(abs(w - 0.25) < 1e-9 for w in weights)

    def test_returns_series_indexed_by_ticker(self):
        sec = _make_securities()
        weights = compute_benchmark_weights(sec)
        assert isinstance(weights, pd.Series)
        assert set(weights.index) == set(sec["ticker"])

    def test_raises_on_empty_securities(self):
        with pytest.raises(ValueError, match="empty"):
            compute_benchmark_weights(pd.DataFrame(columns=["ticker", "sector"]))

    def test_raises_on_missing_columns(self):
        with pytest.raises(ValueError, match="missing columns"):
            compute_benchmark_weights(pd.DataFrame({"ticker": ["AAPL"]}))


# ---------------------------------------------------------------------------
# TestConstructBasket
# ---------------------------------------------------------------------------

class TestConstructBasket:
    def setup_method(self):
        self.sec = _make_securities(n_sectors=3, stocks_per_sector=4)
        self.bench = compute_benchmark_weights(self.sec)

    def test_weights_sum_to_1(self):
        basket = construct_basket(self.bench, self.sec, n_stocks=6)
        assert abs(basket.sum() - 1.0) < 1e-9

    def test_basket_has_correct_size(self):
        basket = construct_basket(self.bench, self.sec, n_stocks=6)
        assert len(basket) == 6

    def test_sector_exclusion_removes_sector(self):
        basket = construct_basket(
            self.bench, self.sec, n_stocks=6, excluded_sectors=["Sector0"]
        )
        included_tickers = set(basket.index)
        sector0_tickers = set(self.sec.loc[self.sec["sector"] == "Sector0", "ticker"])
        assert included_tickers.isdisjoint(sector0_tickers)

    def test_sector_exclusion_weights_still_sum_to_1(self):
        basket = construct_basket(
            self.bench, self.sec, n_stocks=6, excluded_sectors=["Sector1"]
        )
        assert abs(basket.sum() - 1.0) < 1e-9

    def test_max_weight_constraint_respected(self):
        # 6 positions, cap=0.20 → max sum = 1.20 > 1.0, so this is feasible.
        cap = 0.20
        basket = construct_basket(
            self.bench, self.sec, n_stocks=6, max_weight_per_position=cap
        )
        assert (basket <= cap + 1e-9).all()

    def test_max_weight_weights_still_sum_to_1(self):
        basket = construct_basket(
            self.bench, self.sec, n_stocks=6, max_weight_per_position=0.20
        )
        assert abs(basket.sum() - 1.0) < 1e-9

    def test_impossible_cap_raises_value_error(self):
        # 6 positions × 0.10 = 0.60 < 1.0 → mathematically impossible
        with pytest.raises(ValueError, match="too restrictive"):
            construct_basket(
                self.bench, self.sec, n_stocks=6, max_weight_per_position=0.10
            )

    def test_n_stocks_larger_than_universe_includes_all(self):
        # 3 sectors * 4 stocks = 12 total; requesting 9999 should give all 12
        basket = construct_basket(self.bench, self.sec, n_stocks=9999)
        assert len(basket) == 12
        assert abs(basket.sum() - 1.0) < 1e-9

    def test_all_sectors_excluded_raises(self):
        with pytest.raises(ValueError, match="No stocks remain"):
            construct_basket(
                self.bench, self.sec,
                excluded_sectors=["Sector0", "Sector1", "Sector2"]
            )

    def test_all_weights_positive(self):
        basket = construct_basket(self.bench, self.sec, n_stocks=6)
        assert (basket > 0).all()

    def test_basket_tickers_are_subset_of_universe(self):
        basket = construct_basket(self.bench, self.sec, n_stocks=6)
        assert set(basket.index).issubset(set(self.sec["ticker"]))


# ---------------------------------------------------------------------------
# TestLoadFunctions
# ---------------------------------------------------------------------------

class TestLoadFunctions:
    def test_load_securities_returns_correct_columns(self, tmp_conn):
        upsert_securities(tmp_conn, [
            {"ticker": "AAPL", "name": "Apple", "sector": "Tech"},
            {"ticker": "MSFT", "name": "Microsoft", "sector": "Tech"},
        ])
        df = load_securities(tmp_conn)
        assert set(df.columns) == {"ticker", "name", "sector"}
        assert len(df) == 2

    def test_load_prices_filters_by_ticker(self, tmp_conn):
        upsert_securities(tmp_conn, [
            {"ticker": "AAPL", "name": "Apple", "sector": "Tech"},
            {"ticker": "MSFT", "name": "Microsoft", "sector": "Tech"},
        ])
        insert_prices(tmp_conn, _make_price_rows("AAPL", n_days=3))
        insert_prices(tmp_conn, _make_price_rows("MSFT", n_days=3))

        result = load_prices(tmp_conn, ["AAPL"], date(2024, 1, 1), date(2024, 12, 31))
        assert set(result["ticker"]) == {"AAPL"}
        assert len(result) == 3

    def test_load_prices_date_range_is_inclusive(self, tmp_conn):
        upsert_securities(tmp_conn, [{"ticker": "AAPL", "name": "Apple", "sector": "Tech"}])
        insert_prices(tmp_conn, _make_price_rows("AAPL", n_days=5, start=date(2024, 1, 2)))

        result = load_prices(tmp_conn, ["AAPL"], date(2024, 1, 2), date(2024, 1, 4))
        # Should include Jan 2, 3, 4 (3 rows)
        assert len(result) == 3

    def test_load_prices_returns_adj_close_column(self, tmp_conn):
        upsert_securities(tmp_conn, [{"ticker": "AAPL", "name": "Apple", "sector": "Tech"}])
        insert_prices(tmp_conn, _make_price_rows("AAPL", n_days=2))

        result = load_prices(tmp_conn, ["AAPL"], date(2024, 1, 1), date(2024, 12, 31))
        assert set(result.columns) == {"ticker", "date", "adj_close"}
