# cleans and validates raw price data before storing
# hard failures raise, soft issues (sparse coverage, duplicates) just warn
# we don't forward-fill missing prices here — that decision belongs to the consumer

import logging
from datetime import date, timedelta

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {"ticker", "date", "open", "high", "low", "close", "volume", "adj_close"}

# US markets ~252 days/year; warn if a ticker is missing more than 20% of that
MAX_MISSING_PCT = 0.20


def validate(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """Clean and validate a price DataFrame. Raises on hard failures, warns on soft ones."""
    _check_required_columns(df)

    df = _drop_duplicates(df)
    df = _drop_invalid_prices(df)
    _check_date_coverage(df, start, end)

    return df.reset_index(drop=True)


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
    # ~252 trading days per year — rough approximation to flag sparse tickers
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
