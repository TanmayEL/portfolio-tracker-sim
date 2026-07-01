"""
Fetch historical daily price data from Yahoo Finance via yfinance.

Design notes:
- We download all tickers in a single batch call (faster than per-ticker loops).
- yfinance returns a MultiIndex DataFrame; we reshape it into a flat
  per-(ticker, date) structure that maps cleanly to our prices table.
- adj_close comes from yfinance's "Close" column when auto_adjust=True,
  which applies split and dividend adjustments automatically.
"""

import logging
from datetime import date

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def fetch_prices(
    tickers: list[str],
    start: date,
    end: date,
) -> pd.DataFrame:
    """
    Download adjusted daily OHLCV data for all tickers over [start, end].

    Returns a DataFrame with columns:
        ticker, date, open, high, low, close, volume, adj_close

    yfinance note: when auto_adjust=True, all OHLC columns are already
    split/dividend adjusted, so 'close' == 'adj_close'. We store both
    for schema compatibility and clarity.
    """
    logger.info(
        "Fetching %d tickers from %s to %s ...", len(tickers), start, end
    )

    raw: pd.DataFrame = yf.download(
        tickers=tickers,
        start=start.isoformat(),
        end=end.isoformat(),
        auto_adjust=True,   # adjusts all OHLC + volume for splits/dividends
        progress=False,
        group_by="ticker",  # MultiIndex: (field, ticker) or (ticker, field)
    )

    if raw.empty:
        raise ValueError("yfinance returned no data. Check tickers and date range.")

    rows = _reshape(raw, tickers)
    logger.info("Fetched %d price rows for %d tickers.", len(rows), rows["ticker"].nunique())
    return rows


def _reshape(raw: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    """
    Flatten the MultiIndex DataFrame returned by yfinance into a tidy
    (ticker, date, open, high, low, close, volume, adj_close) table.

    yfinance column structure with group_by="ticker":
      - Single ticker  → columns are field names directly
      - Multiple tickers → MultiIndex columns: (ticker, field)
    """
    records = []

    if len(tickers) == 1:
        # Single-ticker path: columns are plain field names
        df = raw.copy()
        df["ticker"] = tickers[0]
        df = df.reset_index().rename(columns={"Date": "date", "index": "date"})
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df.rename(columns={
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume",
        })
        df["adj_close"] = df["close"]
        return df[["ticker", "date", "open", "high", "low", "close", "volume", "adj_close"]]

    # Multi-ticker path: top-level columns are tickers
    for ticker in tickers:
        if ticker not in raw.columns.get_level_values(0):
            logger.warning("Ticker %s missing from yfinance response — skipping.", ticker)
            continue

        sub = raw[ticker].copy()
        sub = sub.dropna(how="all")
        if sub.empty:
            logger.warning("Ticker %s has no data rows — skipping.", ticker)
            continue

        sub = sub.reset_index().rename(columns={"Date": "date", "Datetime": "date"})
        sub["date"] = pd.to_datetime(sub["date"]).dt.date
        sub["ticker"] = ticker
        sub = sub.rename(columns={
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume",
        })
        sub["adj_close"] = sub["close"]

        records.append(
            sub[["ticker", "date", "open", "high", "low", "close", "volume", "adj_close"]]
        )

    if not records:
        raise ValueError("No valid price data was returned for any ticker.")

    return pd.concat(records, ignore_index=True)
