# builds a subset basket that tracks a benchmark, sector by sector
# not an optimizer — no covariance matrix, no ML, just proportional sampling
# stocks are picked alphabetically within each sector (no ranking signal exists)

import pandas as pd


def construct_basket(
    benchmark_weights: pd.Series,
    securities: pd.DataFrame,
    n_stocks: int = 30,
    excluded_sectors: list[str] | None = None,
    max_weight_per_position: float | None = None,
) -> pd.Series:
    """Returns {ticker: weight} for n_stocks selected from the benchmark universe.

    excluded_sectors: drop entire sectors (e.g. ESG screens)
    max_weight_per_position: hard cap per position, excess redistributed proportionally
    If n_stocks > available universe, all stocks are included.
    """
    excluded = set(excluded_sectors or [])

    eligible = securities[~securities["sector"].isin(excluded)].copy()
    if eligible.empty:
        raise ValueError(f"No stocks remain after applying sector exclusions. Excluded: {excluded}")

    eligible_tickers = set(eligible["ticker"])

    bench = benchmark_weights[benchmark_weights.index.isin(eligible_tickers)].copy()
    bench = bench / bench.sum()  # re-normalize after exclusions

    sector_of = eligible.set_index("ticker")["sector"]
    sector_weights = bench.groupby(sector_of).sum()

    target = min(n_stocks, len(eligible))
    slots = _allocate_slots(sector_weights, target)

    selected: dict[str, float] = {}
    for sector, n_slots in slots.items():
        sector_tickers = sorted(eligible.loc[eligible["sector"] == sector, "ticker"].tolist())
        n_slots = min(n_slots, len(sector_tickers))
        per_stock_weight = sector_weights[sector] / n_slots
        for ticker in sector_tickers[:n_slots]:
            selected[ticker] = per_stock_weight

    basket = pd.Series(selected).sort_index()

    if max_weight_per_position is not None:
        basket = _apply_weight_cap(basket, max_weight_per_position)

    assert abs(basket.sum() - 1.0) < 1e-9, f"basket weights sum to {basket.sum():.10f}, expected 1.0"

    return basket


def _allocate_slots(sector_weights: pd.Series, target: int) -> pd.Series:
    """Assign stock slots to sectors proportional to their weights.

    Every sector gets at least 1. Total slots == target.
    Rounding is corrected by nudging the most over/under-allocated sector one at a time.
    """
    raw = sector_weights * target
    slots = raw.round().clip(lower=1).astype(int)

    for _ in range(len(slots)):
        diff = target - slots.sum()
        if diff == 0:
            break
        if diff > 0:
            slots[(raw - slots).idxmax()] += 1
        else:
            candidates = slots[slots > 1]
            if candidates.empty:
                break
            slots[(slots - raw)[candidates.index].idxmax()] -= 1

    return slots


def _apply_weight_cap(basket: pd.Series, cap: float) -> pd.Series:
    """Cap each position at `cap`, redistributing excess proportionally to uncapped positions.

    Raises ValueError if cap * n_positions < 1.0 (mathematically impossible to sum to 1).
    """
    if cap * len(basket) < 1.0 - 1e-9:
        raise ValueError(
            f"max_weight_per_position={cap} is too restrictive: "
            f"{len(basket)} positions cannot sum to 1.0 when each is capped at {cap} "
            f"(maximum achievable sum = {cap * len(basket):.4f}). "
            f"Use a cap >= {1.0 / len(basket):.4f} for this basket size."
        )
    basket = basket.copy()
    for _ in range(len(basket)):
        over = basket > cap
        if not over.any():
            break
        excess = (basket[over] - cap).sum()
        basket[over] = cap
        under = ~over
        if under.any():
            basket[under] += excess * (basket[under] / basket[under].sum())

    return basket
