"""
Benchmark weight computation for the simplified direct-indexing universe.

Weighting methodology: equal-weight by sector, then equal-weight within sector.
- Each sector receives 1 / n_sectors of the total portfolio weight.
- Within each sector, every stock receives an equal share of that sector's weight.

Limitation: real direct-indexing benchmarks (e.g. S&P 500 replicas) use
float-adjusted market-cap weights — meaning larger companies represent a
proportionally larger slice of the index. We use equal-weighting here because
market-cap data is not available in this simulator. This is a deliberate,
documented simplification, not an oversight.
"""

import pandas as pd


def compute_benchmark_weights(securities: pd.DataFrame) -> pd.Series:
    """
    Compute equal-weight benchmark allocations across the universe.

    Parameters
    ----------
    securities : pd.DataFrame
        Must have columns 'ticker' and 'sector'.
        Typically the output of load_securities() from pipeline/store.py.

    Returns
    -------
    pd.Series
        Index: ticker (str), values: float weights summing to 1.0.
        Sorted alphabetically by ticker for deterministic output.
    """
    if securities.empty:
        raise ValueError("Securities DataFrame is empty — cannot compute benchmark weights.")

    required = {"ticker", "sector"}
    missing = required - set(securities.columns)
    if missing:
        raise ValueError(f"Securities DataFrame missing columns: {missing}")

    n_sectors = securities["sector"].nunique()

    # stocks_in_sector[i] = number of stocks in the same sector as row i
    stocks_in_sector = securities.groupby("sector")["ticker"].transform("count")

    # Each stock's weight = (1/n_sectors) / stocks_in_its_sector
    raw_weights = 1.0 / (n_sectors * stocks_in_sector)

    weights = pd.Series(raw_weights.values, index=securities["ticker"].values)
    weights = weights.sort_index()

    assert abs(weights.sum() - 1.0) < 1e-9, (
        f"Benchmark weights sum to {weights.sum():.10f}, expected 1.0. "
        "This is a bug in compute_benchmark_weights."
    )

    return weights
