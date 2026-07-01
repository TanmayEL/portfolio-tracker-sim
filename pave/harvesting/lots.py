# in-memory tax lot tracking
# a lot = plain dict: lot_id, ticker, purchase_date, quantity, cost_basis_per_share, status
# lot_id here is a transient counter - the real ID is assigned by SQLite on persist

import logging

import pandas as pd

logger = logging.getLogger(__name__)

_LOT_ID_COUNTER = 0  # replaced by DB AUTOINCREMENT on persist

_EMPTY_PNL_COLUMNS = [
    "lot_id", "ticker", "purchase_date", "quantity",
    "cost_basis_per_share", "current_price", "current_value",
    "unrealized_gain_loss", "unrealized_pct",
]


def open_lot(
    lots: list[dict],
    ticker: str,
    purchase_date: str,
    quantity: float,
    cost_basis_per_share: float,
) -> None:
    """Add a new open lot."""
    global _LOT_ID_COUNTER
    _LOT_ID_COUNTER += 1
    lots.append({
        "lot_id":                _LOT_ID_COUNTER,
        "ticker":                ticker,
        "purchase_date":         purchase_date,
        "quantity":              quantity,
        "cost_basis_per_share":  cost_basis_per_share,
        "status":                "open",
    })


def get_open_lots(lots: list[dict], ticker: str | None = None) -> list[dict]:
    """Return open lots, optionally filtered to a single ticker."""
    return [
        lot for lot in lots
        if lot["status"] == "open"
        and (ticker is None or lot["ticker"] == ticker)
    ]


def compute_unrealized_pnl(
    lots: list[dict],
    current_prices: dict[str, float],
) -> pd.DataFrame:
    """P&L for all open lots that have a price today. Always returns a DataFrame (never a list)."""
    rows = []
    for lot in get_open_lots(lots):
        price = current_prices.get(lot["ticker"])
        if price is None:
            continue
        gain_loss = (price - lot["cost_basis_per_share"]) * lot["quantity"]
        pct = (price / lot["cost_basis_per_share"]) - 1.0
        rows.append({
            "lot_id":                lot["lot_id"],
            "ticker":                lot["ticker"],
            "purchase_date":         lot["purchase_date"],
            "quantity":              lot["quantity"],
            "cost_basis_per_share":  lot["cost_basis_per_share"],
            "current_price":         price,
            "current_value":         price * lot["quantity"],
            "unrealized_gain_loss":  gain_loss,
            "unrealized_pct":        pct,
        })

    if not rows:
        return pd.DataFrame(columns=_EMPTY_PNL_COLUMNS)

    return pd.DataFrame(rows)


def mark_harvested(lots: list[dict], lot_id: int) -> None:
    """Set status='harvested'. Raises KeyError if lot_id not found."""
    for lot in lots:
        if lot["lot_id"] == lot_id:
            lot["status"] = "harvested"
            return
    raise KeyError(f"lot_id {lot_id} not found in lots list")
