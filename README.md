# Tax Loss Harvesting Simulator

A direct indexing and tax-loss harvesting simulator built as a portfolio project.

[See the simulation results and analysis](RESULTS.md)

---

## What it does

**Direct indexing** is owning individual stocks rather than a fund. Instead of buying an ETF that tracks the S&P 500, you buy a subset of the same underlying stocks in similar proportions. The key advantage: you can harvest tax losses on individual positions that a fund manager never could.

**Tax-loss harvesting** means selling a position that's fallen in value, realizing the loss as a tax deduction, and buying a similar stock to keep your market exposure intact. The IRS wash-sale rule prevents you from immediately buying back the same ticker, so the replacement has to be something different but economically similar.

This project models that entire workflow:
- Downloads 2 years of daily prices (2023-2024) for a 100-stock universe spanning 11 GICS sectors
- Builds a 30-stock basket that mirrors an equal-weight benchmark, allocated proportionally by sector
- Steps through every trading day, harvesting any lot that's dropped more than 5% and swapping it for an eligible same-sector replacement
- Computes three output metrics: total tax losses harvested, tracking error vs. the benchmark, and portfolio turnover

---

## Limitations

This is a simulation with documented simplifications. Each one is a conscious tradeoff, not an oversight:

| What's simplified | What a production system would do |
|---|---|
| Equal-weight benchmark (no market-cap data available) | Market-cap weights sourced from a data provider |
| Replacement selected alphabetically within same sector | Minimize tracking error using a return covariance matrix |
| Wash-sale window: 30 days post-sale, same ticker only | Full IRS "substantially identical" lookback and lookahead |
| Tax alpha assumes full loss usability | Client-specific modeling: AMT exposure, state tax, carryforward limits |
| Tracking error computed using initial weights throughout | Recompute weights daily from live lot values |
| SQLite, synchronous, single process | PostgreSQL, async request handling, authentication |

---

## Quick start

```bash
# create environment and install dependencies
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt

# populate the database with 2 years of prices from Yahoo Finance (~30s)
python scripts/run_pipeline.py

# start the API
uvicorn pave.api.app:app --reload

# open the interactive docs
# http://localhost:8000/docs
```

---

## Demo (via Swagger UI)

The API has three endpoints meant to be called in order. Open `/docs` and follow these steps:

### 1. `POST /portfolio/construct`
Builds a basket from the stored universe. The defaults (30 stocks, no exclusions) work fine for a quick demo.

```json
{
  "n_stocks": 30,
  "excluded_sectors": [],
  "max_weight_per_position": null
}
```

Copy the `basket` object from the response.

### 2. `POST /simulate/harvest`
Runs the simulation. Paste the basket from step 1 into the request body, then hit Execute. The engine walks through 2 years of daily prices and harvests any position that's down more than 5%.

```json
{
  "basket": { "AAPL": 0.034, "MSFT": 0.034 },
  "initial_portfolio_value": 100000.0,
  "harvest_threshold": 0.05,
  "start_date": "2023-01-01",
  "end_date": "2024-12-31"
}
```

Copy the `simulation_id` from the response.

### 3. `GET /evaluate/{simulation_id}`
Returns the three outcome metrics for the completed run.

```json
{
  "tax_alpha": {
    "total_harvested_loss": -2340.50,
    "tax_alpha_pct": -0.0234
  },
  "tracking_error_annualized": 0.031,
  "turnover": 0.19
}
```

- **tax_alpha_pct**: harvested losses as a share of initial portfolio value (negative means deductible losses, so lower is better)
- **tracking_error_annualized**: annualized standard deviation of daily return differences between the basket and the benchmark
- **turnover**: total sell-side trading volume as a fraction of the initial portfolio

---

## Project structure

```
pave/
  config.py          100-stock universe definition, date range, DB path
  pipeline/          price fetch (yfinance) -> validation -> SQLite persistence
  portfolio/         equal-weight benchmark, proportional basket construction
  harvesting/        in-memory lot tracking, wash-sale rules, simulation engine
  evaluation/        tax alpha, tracking error, turnover calculations
  api/               FastAPI app, Pydantic schemas, DB dependency
  db/schema.sql      4 tables: securities, prices, tax_lots, harvest_events
scripts/
  run_pipeline.py    one-shot data ingestion script
tests/               79 unit and integration tests, no network, no live DB required
```

---

## Tests

```bash
pytest tests/ -v     # 79 tests, no network calls, no live database
```

---

## Stack

Python 3.10 · FastAPI · pandas · yfinance · SQLite (raw sqlite3, no ORM) · pytest
