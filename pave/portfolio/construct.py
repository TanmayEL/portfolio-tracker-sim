"""
Greedy proportional basket construction for direct indexing.

This is NOT an optimizer. There is no covariance matrix, no quadratic
programming, and no ML. The algorithm is deliberately simple so that
every step can be explained in plain English:

  1. Remove any excluded sectors.
  2. Re-normalize the remaining benchmark weights to sum to 1.0.
  3. Allocate stock "slots" to each sector proportional to its weight.
  4. Within each sector, pick stocks alphabetically (we have no ranking
     signal — alphabetical is deterministic and reproducible).
  5. Each selected stock's weight = its sector's weight / slots in sector.
  6. Optionally cap any single position at max_weight_per_position,
     redistributing excess across uncapped positions.

The right question to ask about this approach is not "is it optimal?"
(it isn't) but "is it honest and explainable?" (it is).
"""

import pandas as pd


def construct_basket(
    benchmark_weights: pd.Series,
    securities: pd.DataFrame,
    n_stocks: int = 30,
    excluded_sectors: list[str] | None = None,
    max_weight_per_position: float | None = None,
) -> pd.Series:
    """
    Build a tracking basket by greedy proportional sector sampling.

    Parameters
    ----------
    benchmark_weights : pd.Series
        Ticker-indexed weights from compute_benchmark_weights(). Must sum to 1.0.
    securities : pd.DataFrame
        Must have columns 'ticker' and 'sector'.
    n_stocks : int
        Target basket size. If larger than the available universe after
        exclusions, all available stocks are included.
    excluded_sectors : list[str] | None
        Sectors to remove entirely before constructing the basket (e.g. for
        ethical/ESG screens or client-specific constraints).
    max_weight_per_position : float | None
        Hard cap on any single position weight. Excess weight from capped
        positions is redistributed proportionally to uncapped positions.

    Returns
    -------
    pd.Series
        Index: ticker, values: float weights summing to 1.0.
        Only contains the selected subset of the universe.
    """
    excluded = set(excluded_sectors or [])

    # --- Step 1: Filter to eligible universe ---
    eligible = securities[~securities["sector"].isin(excluded)].copy()
    if eligible.empty:
        raise ValueError(
            "No stocks remain after applying sector exclusions. "
            f"Excluded: {excluded}"
        )

    eligible_tickers = set(eligible["ticker"])

    # --- Step 2: Filter and re-normalize benchmark weights ---
    bench = benchmark_weights[benchmark_weights.index.isin(eligible_tickers)].copy()
    bench = bench / bench.sum()  # re-normalize to 1.0 after dropping excluded sectors

    # --- Step 3: Per-sector aggregated weight and slot allocation ---
    sector_of = eligible.set_index("ticker")["sector"]
    sector_weights = bench.groupby(sector_of).sum()  # total weight per sector

    target = min(n_stocks, len(eligible))
    slots = _allocate_slots(sector_weights, target)

    # --- Step 4 & 5: Select tickers per sector, assign weights ---
    selected: dict[str, float] = {}
    for sector, n_slots in slots.items():
        sector_tickers = sorted(
            eligible.loc[eligible["sector"] == sector, "ticker"].tolist()
        )
        n_slots = min(n_slots, len(sector_tickers))  # can't exceed available
        per_stock_weight = sector_weights[sector] / n_slots
        for ticker in sector_tickers[:n_slots]:
            selected[ticker] = per_stock_weight

    basket = pd.Series(selected).sort_index()

    # --- Step 6: Apply max_weight_per_position cap ---
    if max_weight_per_position is not None:
        basket = _apply_weight_cap(basket, max_weight_per_position)

    assert abs(basket.sum() - 1.0) < 1e-9, (
        f"Basket weights sum to {basket.sum():.10f}, expected 1.0. "
        "This is a bug in construct_basket."
    )

    return basket


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _allocate_slots(sector_weights: pd.Series, target: int) -> pd.Series:
    """
    Distribute `target` stock slots across sectors proportional to their weights.

    Rules:
    - Every sector gets at least 1 slot.
    - Total slots == target.
    - Rounding errors are corrected by incrementing/decrementing the sector
      with the largest fractional surplus/deficit, one at a time.

    This is not an optimizer — it's a deterministic rounding correction.
    """
    raw = sector_weights * target
    slots = raw.round().clip(lower=1).astype(int)

    # Iterative correction: adjust the sector with the most rounding error
    # until total slots matches target. Bounded by n_sectors iterations.
    for _ in range(len(slots)):
        diff = target - slots.sum()
        if diff == 0:
            break
        if diff > 0:
            # Need more slots: increment the sector most "under-allocated"
            gap = raw - slots
            slots[gap.idxmax()] += 1
        else:
            # Need fewer slots: decrement the sector most "over-allocated",
            # but don't go below 1.
            gap = slots - raw
            candidates = slots[slots > 1]
            if candidates.empty:
                break
            slots[gap[candidates.index].idxmax()] -= 1

    return slots


def _apply_weight_cap(basket: pd.Series, cap: float) -> pd.Series:
    """
    Iteratively cap positions at `cap` and redistribute excess weight
    proportionally to uncapped positions.

    Converges in at most len(basket) iterations (each iteration fixes at
    least one violator permanently).

    Raises ValueError if the cap is mathematically impossible (i.e. cap × n_positions < 1.0),
    which would cause weight to disappear with nowhere to redistribute it.
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
