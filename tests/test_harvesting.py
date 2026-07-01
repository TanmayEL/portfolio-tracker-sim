"""
Tests for the tax-loss harvesting modules: lots, wash_sale, and simulate.

All tests use synthetic data — no live DB or network required.
The integration tests (TestSimulation) use a temporary SQLite DB via pytest's
tmp_path fixture, following the same pattern as test_pipeline.py.

Synthetic simulation setup:
    3 tickers in the same sector: AAA, BBB, CCC
    10 calendar days starting 2024-01-02
    AAA: 100 → 95 → 80 (drop of 20% by day 3 — triggers 5% threshold)
    BBB: flat at 200 throughout (first alphabetical replacement candidate)
    CCC: flat at 150 throughout (second replacement candidate)
"""

from datetime import date, timedelta

import pandas as pd
import pytest

from pave.harvesting.lots import (
    compute_unrealized_pnl,
    get_open_lots,
    mark_harvested,
    open_lot,
)
from pave.harvesting.simulate import run_simulation
from pave.harvesting.wash_sale import (
    get_eligible_replacements,
    is_blocked,
    record_sale,
)
from pave.pipeline.store import (
    init_db,
    load_harvest_events,
    load_lots,
    upsert_securities,
)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_conn(tmp_path):
    db_path = tmp_path / "test_sim.db"
    conn = init_db(db_path)
    upsert_securities(conn, [
        {"ticker": "AAA", "name": "Alpha Corp",  "sector": "Tech"},
        {"ticker": "BBB", "name": "Beta Corp",   "sector": "Tech"},
        {"ticker": "CCC", "name": "Gamma Corp",  "sector": "Tech"},
    ])
    yield conn
    conn.close()


def _make_synthetic_prices() -> pd.DataFrame:
    """
    3 tickers over 10 days. AAA drops −20% by day 3 to trigger harvesting.
    BBB and CCC stay flat throughout.
    """
    dates = [date(2024, 1, 2) + timedelta(days=i) for i in range(10)]
    rows = []
    for i, d in enumerate(dates):
        aaa_price = 100.0 if i == 0 else (95.0 if i == 1 else 80.0)
        rows.append({"ticker": "AAA", "date": d.isoformat(), "adj_close": aaa_price})
        rows.append({"ticker": "BBB", "date": d.isoformat(), "adj_close": 200.0})
        rows.append({"ticker": "CCC", "date": d.isoformat(), "adj_close": 150.0})
    return pd.DataFrame(rows)


def _make_synthetic_securities() -> pd.DataFrame:
    return pd.DataFrame([
        {"ticker": "AAA", "name": "Alpha Corp",  "sector": "Tech"},
        {"ticker": "BBB", "name": "Beta Corp",   "sector": "Tech"},
        {"ticker": "CCC", "name": "Gamma Corp",  "sector": "Tech"},
    ])


def _run(conn):
    return run_simulation(
        conn=conn,
        basket=pd.Series({"AAA": 0.5, "BBB": 0.3, "CCC": 0.2}),
        prices_df=_make_synthetic_prices(),
        securities=_make_synthetic_securities(),
        initial_portfolio_value=10_000.0,
        harvest_threshold=0.05,
    )


# ---------------------------------------------------------------------------
# TestWashSale
# ---------------------------------------------------------------------------

class TestWashSale:
    def test_blocked_within_30_days(self):
        r = {}
        record_sale(r, "AAA", date(2024, 3, 1))
        assert is_blocked(r, "AAA", date(2024, 3, 15))

    def test_blocked_on_exact_day_30(self):
        r = {}
        record_sale(r, "AAA", date(2024, 3, 1))
        assert is_blocked(r, "AAA", date(2024, 3, 31))  # day 30 inclusive

    def test_not_blocked_after_30_days(self):
        r = {}
        record_sale(r, "AAA", date(2024, 3, 1))
        assert not is_blocked(r, "AAA", date(2024, 4, 1))  # day 31 — clear

    def test_not_blocked_different_ticker(self):
        r = {}
        record_sale(r, "AAA", date(2024, 3, 1))
        assert not is_blocked(r, "BBB", date(2024, 3, 10))

    def test_not_blocked_with_no_prior_sale(self):
        assert not is_blocked({}, "AAA", date(2024, 3, 1))

    def test_eligible_replacements_filters_blocked(self):
        r = {}
        record_sale(r, "AAA", date(2024, 3, 1))
        result = get_eligible_replacements(r, ["AAA", "BBB", "CCC"], date(2024, 3, 10))
        assert "AAA" not in result
        assert set(result) == {"BBB", "CCC"}

    def test_eligible_replacements_all_clear(self):
        candidates = ["AAA", "BBB", "CCC"]
        result = get_eligible_replacements({}, candidates, date(2024, 3, 10))
        assert result == candidates  # order preserved


# ---------------------------------------------------------------------------
# TestLots
# ---------------------------------------------------------------------------

class TestLots:
    def test_open_lot_adds_entry(self):
        lots = []
        open_lot(lots, "AAA", "2024-01-02", 10.0, 100.0)
        assert len(lots) == 1
        lot = lots[0]
        assert lot["ticker"] == "AAA"
        assert lot["quantity"] == 10.0
        assert lot["cost_basis_per_share"] == 100.0
        assert lot["status"] == "open"

    def test_get_open_lots_excludes_harvested(self):
        lots = []
        open_lot(lots, "AAA", "2024-01-02", 10.0, 100.0)
        open_lot(lots, "BBB", "2024-01-02", 5.0, 200.0)
        lots[0]["status"] = "harvested"
        result = get_open_lots(lots)
        assert len(result) == 1
        assert result[0]["ticker"] == "BBB"

    def test_get_open_lots_filters_by_ticker(self):
        lots = []
        open_lot(lots, "AAA", "2024-01-02", 10.0, 100.0)
        open_lot(lots, "BBB", "2024-01-02", 5.0, 200.0)
        result = get_open_lots(lots, ticker="AAA")
        assert len(result) == 1
        assert result[0]["ticker"] == "AAA"

    def test_compute_unrealized_pnl_loss_scenario(self):
        lots = []
        open_lot(lots, "AAA", "2024-01-02", 10.0, 100.0)  # paid $100
        pnl = compute_unrealized_pnl(lots, {"AAA": 80.0})   # now $80
        assert len(pnl) == 1
        row = pnl.iloc[0]
        assert abs(row["unrealized_gain_loss"] - (-200.0)) < 1e-6  # (80-100)*10 = -200
        assert abs(row["unrealized_pct"] - (-0.20)) < 1e-6

    def test_compute_unrealized_pnl_gain_scenario(self):
        lots = []
        open_lot(lots, "BBB", "2024-01-02", 5.0, 200.0)   # paid $200
        pnl = compute_unrealized_pnl(lots, {"BBB": 250.0}) # now $250
        row = pnl.iloc[0]
        assert abs(row["unrealized_gain_loss"] - 250.0) < 1e-6  # (250-200)*5 = 250
        assert abs(row["unrealized_pct"] - 0.25) < 1e-6

    def test_compute_unrealized_pnl_skips_missing_price(self):
        lots = []
        open_lot(lots, "AAA", "2024-01-02", 10.0, 100.0)
        pnl = compute_unrealized_pnl(lots, {})
        assert pnl.empty

    def test_compute_unrealized_pnl_returns_correct_columns_when_empty(self):
        pnl = compute_unrealized_pnl([], {})
        expected = {
            "lot_id", "ticker", "purchase_date", "quantity",
            "cost_basis_per_share", "current_price", "current_value",
            "unrealized_gain_loss", "unrealized_pct",
        }
        assert set(pnl.columns) == expected

    def test_mark_harvested_changes_status(self):
        lots = []
        open_lot(lots, "AAA", "2024-01-02", 10.0, 100.0)
        lot_id = lots[0]["lot_id"]
        mark_harvested(lots, lot_id)
        assert lots[0]["status"] == "harvested"
        assert len(get_open_lots(lots)) == 0

    def test_mark_harvested_raises_on_unknown_id(self):
        with pytest.raises(KeyError):
            mark_harvested([], 999)


# ---------------------------------------------------------------------------
# TestSimulation (integration)
# ---------------------------------------------------------------------------

class TestSimulation:
    def test_returns_simulation_id_string(self, tmp_conn):
        sim_id = _run(tmp_conn)
        assert isinstance(sim_id, str)
        assert len(sim_id) == 36  # UUID4 length

    def test_at_least_one_harvest_event_recorded(self, tmp_conn):
        sim_id = _run(tmp_conn)
        events = load_harvest_events(tmp_conn, sim_id)
        assert len(events) >= 1

    def test_aaa_lot_is_harvested(self, tmp_conn):
        sim_id = _run(tmp_conn)
        lots = load_lots(tmp_conn, sim_id)
        aaa_lots = lots[lots["ticker"] == "AAA"]
        assert (aaa_lots["status"] == "harvested").any()

    def test_replacement_lot_was_opened(self, tmp_conn):
        sim_id = _run(tmp_conn)
        events = load_harvest_events(tmp_conn, sim_id)
        lots = load_lots(tmp_conn, sim_id)
        replacement = events.iloc[0]["replacement_ticker"]
        assert replacement in lots["ticker"].values

    def test_sold_ticker_is_aaa(self, tmp_conn):
        sim_id = _run(tmp_conn)
        events = load_harvest_events(tmp_conn, sim_id)
        assert "AAA" in events["sold_ticker"].values

    def test_replacement_ticker_differs_from_sold(self, tmp_conn):
        sim_id = _run(tmp_conn)
        events = load_harvest_events(tmp_conn, sim_id)
        for _, row in events.iterrows():
            assert row["replacement_ticker"] != row["sold_ticker"]

    def test_realized_loss_is_negative(self, tmp_conn):
        sim_id = _run(tmp_conn)
        events = load_harvest_events(tmp_conn, sim_id)
        assert (events["realized_loss"] < 0).all()

    def test_wash_sale_prevents_aaa_repurchase_within_30_days(self, tmp_conn):
        sim_id = _run(tmp_conn)
        events = load_harvest_events(tmp_conn, sim_id)
        aaa_sales = events[events["sold_ticker"] == "AAA"]
        if aaa_sales.empty:
            pytest.skip("AAA was never harvested in this run")

        sale_date = date.fromisoformat(aaa_sales.iloc[0]["event_date"])
        window_end = sale_date + timedelta(days=30)

        subsequent = events[
            (events["event_date"] > sale_date.isoformat()) &
            (events["event_date"] <= window_end.isoformat())
        ]
        assert "AAA" not in subsequent["replacement_ticker"].values

    def test_lots_table_populated(self, tmp_conn):
        sim_id = _run(tmp_conn)
        lots = load_lots(tmp_conn, sim_id)
        assert len(lots) >= 3  # at least the 3 initial lots

    def test_two_runs_produce_different_simulation_ids(self, tmp_conn):
        sim_id_1 = _run(tmp_conn)
        sim_id_2 = _run(tmp_conn)
        assert sim_id_1 != sim_id_2

    def test_simulation_ids_isolate_results(self, tmp_conn):
        sim_id_1 = _run(tmp_conn)
        sim_id_2 = _run(tmp_conn)
        events_1 = load_harvest_events(tmp_conn, sim_id_1)
        events_2 = load_harvest_events(tmp_conn, sim_id_2)
        # Each run's events reference only that run's simulation_id
        assert (events_1["simulation_id"] == sim_id_1).all()
        assert (events_2["simulation_id"] == sim_id_2).all()
