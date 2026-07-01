# three metrics that tell you if harvesting was worth it:
# tax alpha  — how much loss was harvested vs initial portfolio value
# tracking error — how far the basket drifted from the benchmark (annualized)
# turnover — how much trading the harvesting required

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def compute_tax_alpha(
    harvest_events_df: pd.DataFrame,
    initial_portfolio_value: float,
) -> dict:
    # sum of realized_loss (negative = losses = good for tax purposes)
    # tax_alpha_pct is loss as a fraction of initial portfolio, e.g. -0.02 means 2% harvested
    # simplification: assumes full usability — no wash-sale disallowance at portfolio level,
    # no AMT, no state tax. caller applies their own marginal rate if needed.
    if harvest_events_df.empty:
        return {"total_harvested_loss": 0.0, "tax_alpha_pct": 0.0}

    total = float(harvest_events_df["realized_loss"].sum())
    return {
        "total_harvested_loss": total,
        "tax_alpha_pct": total / initial_portfolio_value,
    }


def compute_tracking_error(
    prices_df: pd.DataFrame,
    basket_weights: pd.Series,
    benchmark_weights: pd.Series,
) -> float:
    # annualized std of daily (basket_return - benchmark_return)
    # both weight series must sum to 1
    # simplification: uses initial weights throughout — ignores lot changes and drift over time
    prices_wide = prices_df.pivot(index="date", columns="ticker", values="adj_close")

    if len(prices_wide) < 2:
        raise ValueError(
            f"Need at least 2 dates to compute returns; got {len(prices_wide)}."
        )

    daily_returns = prices_wide.pct_change().dropna(how="all")

    basket_tickers = basket_weights.index.intersection(prices_wide.columns)
    bench_tickers = benchmark_weights.index.intersection(prices_wide.columns)

    basket_rets = (
        daily_returns[basket_tickers].fillna(0)
        @ basket_weights[basket_tickers].values
    )
    bench_rets = (
        daily_returns[bench_tickers].fillna(0)
        @ benchmark_weights[bench_tickers].values
    )

    diff = basket_rets - bench_rets
    return float(diff.std() * (252 ** 0.5))


def compute_turnover(
    harvest_events_df: pd.DataFrame,
    initial_portfolio_value: float,
) -> float:
    # sell-side only: each harvest sells one lot and buys another of equal $ value
    # so one-sided already captures the full trading cost signal without double-counting
    if harvest_events_df.empty:
        return 0.0

    traded = (
        harvest_events_df["sold_quantity"] * harvest_events_df["sold_price"]
    ).sum()
    return float(traded / initial_portfolio_value)
