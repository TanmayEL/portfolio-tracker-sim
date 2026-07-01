import pandas as pd
import pytest

from pave.evaluation.metrics import (
    compute_tax_alpha,
    compute_tracking_error,
    compute_turnover,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_prices(tickers: list[str], n_days: int = 5, start_price: float = 100.0) -> pd.DataFrame:
    dates = [f"2024-01-{i + 2:02d}" for i in range(n_days)]
    rows = []
    for t in tickers:
        price = start_price
        for d in dates:
            rows.append({"ticker": t, "date": d, "adj_close": price})
            price *= 1.01
    return pd.DataFrame(rows)


def _make_events(n: int = 1, loss_per: float = -500.0, qty: float = 10.0, price: float = 100.0) -> pd.DataFrame:
    return pd.DataFrame([
        {"realized_loss": loss_per, "sold_quantity": qty, "sold_price": price}
        for _ in range(n)
    ])


# ---------------------------------------------------------------------------
# TestTaxAlpha
# ---------------------------------------------------------------------------

class TestTaxAlpha:
    def test_empty_events_returns_zeros(self):
        result = compute_tax_alpha(pd.DataFrame(columns=["realized_loss"]), 10_000.0)
        assert result["total_harvested_loss"] == 0.0
        assert result["tax_alpha_pct"] == 0.0

    def test_single_event_correct_pct(self):
        events = _make_events(n=1, loss_per=-500.0)
        result = compute_tax_alpha(events, 10_000.0)
        assert abs(result["total_harvested_loss"] - (-500.0)) < 1e-9
        assert abs(result["tax_alpha_pct"] - (-0.05)) < 1e-9

    def test_multiple_events_sum_correctly(self):
        events = _make_events(n=3, loss_per=-200.0)
        result = compute_tax_alpha(events, 10_000.0)
        assert abs(result["total_harvested_loss"] - (-600.0)) < 1e-9
        assert abs(result["tax_alpha_pct"] - (-0.06)) < 1e-9

    def test_result_has_correct_keys(self):
        result = compute_tax_alpha(_make_events(), 10_000.0)
        assert "total_harvested_loss" in result
        assert "tax_alpha_pct" in result

    def test_result_values_are_floats(self):
        result = compute_tax_alpha(_make_events(), 10_000.0)
        assert isinstance(result["total_harvested_loss"], float)
        assert isinstance(result["tax_alpha_pct"], float)


# ---------------------------------------------------------------------------
# TestTrackingError
# ---------------------------------------------------------------------------

class TestTrackingError:
    def test_identical_basket_and_benchmark_gives_zero(self):
        # same tickers, same weights → daily diff is always 0
        tickers = ["AAA", "BBB", "CCC"]
        prices = _make_prices(tickers, n_days=10)
        weights = pd.Series({"AAA": 1/3, "BBB": 1/3, "CCC": 1/3})
        te = compute_tracking_error(prices, weights, weights)
        assert abs(te) < 1e-9

    def test_diverging_basket_gives_positive_te(self):
        # AAA and BBB have different volatile daily moves → return diff has non-zero variance
        dates = [f"2024-01-{i + 2:02d}" for i in range(10)]
        aaa_prices = [100, 102, 99, 103, 101, 105, 98, 104, 107, 103]
        bbb_prices = [100, 98,  103, 100, 106, 102, 108, 104, 100, 107]
        rows = (
            [{"ticker": "AAA", "date": d, "adj_close": p} for d, p in zip(dates, aaa_prices)]
            + [{"ticker": "BBB", "date": d, "adj_close": p} for d, p in zip(dates, bbb_prices)]
        )
        prices = pd.DataFrame(rows)
        basket_w = pd.Series({"AAA": 1.0})
        bench_w = pd.Series({"BBB": 1.0})
        te = compute_tracking_error(prices, basket_w, bench_w)
        assert te > 0

    def test_returns_float(self):
        prices = _make_prices(["AAA", "BBB"])
        w = pd.Series({"AAA": 0.5, "BBB": 0.5})
        assert isinstance(compute_tracking_error(prices, w, w), float)

    def test_annualization(self):
        # compute manually and compare
        tickers = ["AAA", "BBB"]
        prices = _make_prices(tickers, n_days=10)
        basket_w = pd.Series({"AAA": 1.0, "BBB": 0.0})
        bench_w = pd.Series({"AAA": 0.0, "BBB": 1.0})

        wide = prices.pivot(index="date", columns="ticker", values="adj_close")
        rets = wide.pct_change().dropna(how="all")
        diff = rets["AAA"] - rets["BBB"]
        expected = float(diff.std() * (252 ** 0.5))

        result = compute_tracking_error(prices, basket_w, bench_w)
        assert abs(result - expected) < 1e-9

    def test_raises_with_fewer_than_2_dates(self):
        prices = _make_prices(["AAA"], n_days=1)
        w = pd.Series({"AAA": 1.0})
        with pytest.raises(ValueError, match="at least 2 dates"):
            compute_tracking_error(prices, w, w)


# ---------------------------------------------------------------------------
# TestTurnover
# ---------------------------------------------------------------------------

class TestTurnover:
    def test_empty_events_returns_zero(self):
        result = compute_turnover(pd.DataFrame(columns=["sold_quantity", "sold_price"]), 10_000.0)
        assert result == 0.0

    def test_single_event_correct_ratio(self):
        # sold 10 shares at $100 = $1000 traded, portfolio = $10000 → 0.10
        events = _make_events(n=1, qty=10.0, price=100.0)
        result = compute_turnover(events, 10_000.0)
        assert abs(result - 0.10) < 1e-9

    def test_multiple_events_sum_correctly(self):
        events = _make_events(n=3, qty=10.0, price=100.0)  # 3 × $1000 = $3000
        result = compute_turnover(events, 10_000.0)
        assert abs(result - 0.30) < 1e-9

    def test_returns_float(self):
        result = compute_turnover(_make_events(), 10_000.0)
        assert isinstance(result, float)
