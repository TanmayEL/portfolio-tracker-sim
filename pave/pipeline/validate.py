"""
Validation and cleaning for raw price data.

What we check and why:
1. Required columns present — fail fast if fetch reshaping broke.
2. No negative prices — a negative adj_close is physically impossible and
   almost always a data error (bad corporate action adjustment).
3. No zero adj_close — zero price implies the security was worthless/delisted;
   we drop those rows rather than letting them corrupt return calculations.
4. Missing date coverage — if a ticker is missing more than MAX_MISSING_PCT of
   expected trading days, we warn loudly. We do NOT drop the ticker
   automatically because missing data could be a yfinance gap vs. a real
   delisting; the operator should decide.
5. Duplicate (ticker, date) pairs — keep the first occurrence and warn.

We do NOT attempt to fill forward missing prices here. That decision
(fill vs. drop vs. flag) is left to the consumer of the data (e.g., the
simulation engine), because the right choice depends on the use case.
"""

import logging
from datetime import date, timedelta

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {"ticker", "date", "open", "high", "low", "close", "volume", "adj_close"}

# Warn if a ticker is missing more than this fraction of expected trading days.
# US markets are open ~252 days/year; we use a generous 20% threshold since
# yfinance occasionally has gaps for less-liquid names.
MAX_MISSING_PCT = 0.20


def validate(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """
    Clean and validate a price DataFrame. Returns the cleaned DataFrame.
    Raises ValueError for hard failures; logs warnings for soft issues.
    """
    _check_required_columns(df)

    df = _drop_duplicates(df)
    df = _drop_invalid_prices(df)
    _check_date_coverage(df, start, end)

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _check_required_columns(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Price DataFrame missing required columns: {missing}")


def _drop_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    dupes = df.duplicated(subset=["ticker", "date"])
    if dupes.any():
        n = dupes.sum()
        logger.warning("Dropping %d duplicate (ticker, date) rows.", n)
        df = df[~dupes]
    return df


def _drop_invalid_prices(df: pd.DataFrame) -> pd.DataFrame:
    mask_zero = df["adj_close"] == 0
    mask_negative = df["adj_close"] < 0
    mask_null = df["adj_close"].isna()

    bad = mask_zero | mask_negative | mask_null
    if bad.any():
        n = bad.sum()
        logger.warning(
            "Dropping %d rows with invalid adj_close (zero, negative, or null).", n
        )
        df = df[~bad]
    return df


def _check_date_coverage(df: pd.DataFrame, start: date, end: date) -> None:
    """
    Estimate expected trading days in the window (approximation: ~252/year).
    Flag any ticker that is missing more than MAX_MISSING_PCT of that count.
    """
    # Count calendar days and scale to approximate trading days.
    calendar_days = (end - start).days + 1
    approx_trading_days = int(calendar_days * 252 / 365)

    counts = df.groupby("ticker")["date"].count()
    low_coverage = counts[counts < approx_trading_days * (1 - MAX_MISSING_PCT)]

    for ticker, count in low_coverage.items():
        pct_missing = 1 - count / approx_trading_days
        logger.warning(
            "Ticker %s has only %d price rows (~%.0f%% missing). "
            "Possible delisting or data gap.",
            ticker, count, pct_missing * 100,
        )
