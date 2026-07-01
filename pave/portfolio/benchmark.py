# equal-weight benchmark: each sector gets 1/n_sectors, stocks within a sector split evenly
# real indexes use market-cap weights — we can't do that without market-cap data, so this is
# the honest simplification

import pandas as pd


def compute_benchmark_weights(securities: pd.DataFrame) -> pd.Series:
    """Returns a Series of {ticker: weight} summing to 1.0.

    securities needs 'ticker' and 'sector' columns (from load_securities()).
    """
    if securities.empty:
        raise ValueError("Securities DataFrame is empty — cannot compute benchmark weights.")

    required = {"ticker", "sector"}
    missing = required - set(securities.columns)
    if missing:
        raise ValueError(f"Securities DataFrame missing columns: {missing}")

    n_sectors = securities["sector"].nunique()
    stocks_in_sector = securities.groupby("sector")["ticker"].transform("count")
    raw_weights = 1.0 / (n_sectors * stocks_in_sector)

    weights = pd.Series(raw_weights.values, index=securities["ticker"].values)
    weights = weights.sort_index()

    assert abs(weights.sum() - 1.0) < 1e-9, f"weights sum to {weights.sum():.10f}, expected 1.0"

    return weights
