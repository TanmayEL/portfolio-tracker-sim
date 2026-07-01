# downloads historical prices from Yahoo Finance via yfinance
# single batch call for all tickers, then reshapes the MultiIndex output into
# a flat (ticker, date, ...) table. auto_adjust=True handles splits/dividends.

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
    """Download adjusted daily OHLCV for all tickers over [start, end].

    Returns columns: ticker, date, open, high, low, close, volume, adj_close.
    With auto_adjust=True, close == adj_close — stored both for clarity.
    """
    logger.info(
        "Fetching %d tickers from %s to %s ...", len(tickers), start, end
    )

    raw: pd.DataFrame = yf.download(
        tickers=tickers,
        start=start.isoformat(),
        end=end.isoformat(),
        auto_adjust=True,
        progress=False,
        group_by="ticker",
    )

    if raw.empty:
        raise ValueError("yfinance returned no data. Check tickers and date range.")

    rows = _reshape(raw, tickers)
    logger.info("Fetched %d price rows for %d tickers.", len(rows), rows["ticker"].nunique())
    return rows


def _reshape(raw: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    """Flatten yfinance's MultiIndex output into a tidy per-(ticker, date) table.

    Single ticker → plain columns. Multiple tickers → MultiIndex (ticker, field).
    """
    records = []

    if len(tickers) == 1:
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
