# walks forward through trading days, harvests losses above threshold,
# respects wash-sale rules, and persists everything to SQLite at the end
#
# replacement selection: alphabetically first eligible same-sector ticker
# (deterministic and explainable — a real system would use return correlation
# to minimize tracking error, but that needs a covariance matrix we don't have)

import logging
import sqlite3
import uuid
from datetime import date

import pandas as pd

from pave.harvesting.lots import (
    compute_unrealized_pnl,
    get_open_lots,
    mark_harvested,
    open_lot,
)
from pave.harvesting.wash_sale import get_eligible_replacements, record_sale, is_blocked
from pave.pipeline.store import insert_harvest_events, insert_lots

logger = logging.getLogger(__name__)


def run_simulation(
    conn: sqlite3.Connection,
    basket: pd.Series,
    prices_df: pd.DataFrame,
    securities: pd.DataFrame,
    initial_portfolio_value: float = 100_000.0,
    harvest_threshold: float = 0.05,
    simulation_id: str | None = None,
) -> str:
    """Run the simulation and persist results. Returns the simulation_id.

    basket: ticker → weight from construct_basket()
    prices_df: ticker, date, adj_close — needs at least 2 trading days
    securities: ticker, sector — used to find same-sector replacements
    harvest_threshold: harvest when unrealized loss exceeds this fraction (default 5%)
    simulation_id: auto-generated UUID if not provided
    """
    if simulation_id is None:
        simulation_id = str(uuid.uuid4())

    logger.info("Starting simulation %s", simulation_id)

    sector_of: dict[str, str] = securities.set_index("ticker")["sector"].to_dict()
    sector_members: dict[str, list[str]] = {
        sector: sorted(group["ticker"].tolist())
        for sector, group in securities.groupby("sector")
    }

    # pivot to (date × ticker) so per-day price lookup is O(1)
    prices_wide = prices_df.pivot(index="date", columns="ticker", values="adj_close")
    sorted_dates: list[str] = sorted(prices_wide.index.tolist())

    if len(sorted_dates) < 2:
        raise ValueError(
            f"prices_df must contain at least 2 trading days; got {len(sorted_dates)}."
        )

    first_date = sorted_dates[0]
    first_prices: dict[str, float] = prices_wide.loc[first_date].dropna().to_dict()

    lots: list[dict] = []
    for ticker, weight in basket.items():
        price = first_prices.get(ticker)
        if price is None or price <= 0:
            logger.warning(
                "No price for %s on %s — skipping initial lot.", ticker, first_date
            )
            continue
        quantity = (weight * initial_portfolio_value) / price
        open_lot(lots, ticker, first_date, quantity, price)

    logger.info(
        "Opened %d initial lots on %s (portfolio value: $%.2f).",
        len(lots), first_date, initial_portfolio_value,
    )

    restrictions: dict = {}      # wash-sale state: ticker → last sale date
    new_events: list[dict] = []

    for trade_date in sorted_dates[1:]:
        day_row = prices_wide.loc[trade_date].dropna()
        if day_row.empty:
            continue

        current_prices: dict[str, float] = day_row.to_dict()
        today: date = date.fromisoformat(trade_date)

        pnl_df = compute_unrealized_pnl(lots, current_prices)
        if pnl_df.empty:
            continue

        # sort alphabetically so processing order is deterministic
        harvest_candidates = (
            pnl_df[pnl_df["unrealized_pct"] < -harvest_threshold]
            .sort_values("ticker")
        )

        for _, row in harvest_candidates.iterrows():
            ticker = row["ticker"]
            lot_id = int(row["lot_id"])

            if is_blocked(restrictions, ticker, today):
                logger.debug(
                    "Skipping %s on %s — wash-sale blocked.", ticker, trade_date
                )
                continue

            replacement = _pick_replacement(
                sold_ticker=ticker,
                sector_of=sector_of,
                sector_members=sector_members,
                restrictions=restrictions,
                today=today,
            )
            if replacement is None:
                logger.warning(
                    "No valid replacement for %s on %s — harvest skipped.",
                    ticker, trade_date,
                )
                continue

            replacement_price = current_prices.get(replacement)
            if replacement_price is None:
                logger.warning(
                    "Replacement %s has no price on %s — harvest skipped.",
                    replacement, trade_date,
                )
                continue

            sold_price: float = row["current_price"]
            quantity: float = row["quantity"]
            realized_loss: float = (sold_price - row["cost_basis_per_share"]) * quantity

            mark_harvested(lots, lot_id)
            record_sale(restrictions, ticker, today)

            # preserve dollar value when opening the replacement
            replacement_quantity = (sold_price * quantity) / replacement_price
            open_lot(lots, replacement, trade_date, replacement_quantity, replacement_price)

            new_events.append({
                "simulation_id":          simulation_id,
                "event_date":             trade_date,
                "sold_ticker":            ticker,
                "sold_lot_id":            lot_id,
                "sold_quantity":          quantity,
                "sold_price":             sold_price,
                "realized_loss":          realized_loss,
                "replacement_ticker":     replacement,
                "replacement_cost_basis": replacement_price,
            })

            logger.info(
                "Harvested %s → %s on %s | realized_loss=%.2f (%.1f%%)",
                ticker, replacement, trade_date,
                realized_loss, row["unrealized_pct"] * 100,
            )

    insert_lots(conn, lots, simulation_id)
    insert_harvest_events(conn, new_events, simulation_id)

    logger.info(
        "Simulation %s complete: %d lots, %d harvest events.",
        simulation_id, len(lots), len(new_events),
    )
    return simulation_id


def _pick_replacement(
    sold_ticker: str,
    sector_of: dict[str, str],
    sector_members: dict[str, list[str]],
    restrictions: dict,
    today: date,
) -> str | None:
    """Alphabetically first same-sector ticker that isn't sold_ticker and isn't wash-sale blocked."""
    sector = sector_of.get(sold_ticker)
    if sector is None:
        return None

    candidates = [t for t in sector_members.get(sector, []) if t != sold_ticker]
    eligible = get_eligible_replacements(restrictions, candidates, today)
    return eligible[0] if eligible else None
