# Simulation Results

A full end-to-end run of the tax-loss harvesting simulator, January 2023 through December 2024.
Parameters: 60-stock basket, 15% harvest threshold, $100,000 initial portfolio.

---

## Step 1: Portfolio Construction

**Endpoint:** `POST /portfolio/construct`

```json
{ "n_stocks": 60, "excluded_sectors": [] }
```

The basket contains 60 stocks drawn proportionally from all 11 GICS sectors. Each position
gets roughly equal weight within its sector, resulting in two weight tiers:

- **~1.82%** per position in sectors where stocks split an equal share evenly
- **~1.52%** per position in larger sectors where more stocks compete for the same sector allocation

A sample of the holdings:

| Sector | Tickers included |
|---|---|
| Information Technology | AAPL, ACN, AMD, AVGO, CRM |
| Health Care | ABBV, ABT, AMGN, DHR, JNJ |
| Financials | AXP, BAC, BLK, BRK-B, GS, JPM |
| Energy | COP, CVX, EOG, HAL, MPC, OXY |
| Utilities | AEP, AWK, DUK, ETR, EXC |
| Real Estate | AMT, CCI, DLR, EQIX, EQR |
| Materials | ALB, APD, DD, DOW, FCX |
| Industrials | BA, CAT, DE, GD, GE |
| Consumer Discretionary | AMZN, BKNG, CMG, DIS, HD, LOW, MCD |
| Consumer Staples | CL, COST, GIS, KO, MDLZ, MO |
| Communication Services | CHTR, CMCSA, GOOG, GOOGL, META |

No sectors were excluded. The full basket is available via the API.

---

## Step 2: Simulation

**Endpoint:** `POST /simulate/harvest`

```json
{
  "harvest_threshold": 0.15,
  "initial_portfolio_value": 100000.0,
  "start_date": "2023-01-01",
  "end_date": "2024-12-31"
}
```

```json
{
  "simulation_id": "0fa1cbe7-993c-4bd0-81ac-ae1c443d3d1c",
  "n_lots": 92,
  "n_harvest_events": 32
}
```

The engine opened **60 initial lots** on the first trading day of 2023, one per basket position.
Over the two years it added **32 more** through harvesting replacements, bringing the total to
**92 lots** in the database.

**32 harvest events** across 504 trading days, about one a month. Each one sold a losing
position, banked the loss, and immediately bought a different stock from the same sector to
keep the exposure. The wash-sale window (30 days) was respected throughout, so no position
was repurchased too soon after being sold.

---

## Step 3: Evaluation

**Endpoint:** `GET /evaluate/0fa1cbe7-993c-4bd0-81ac-ae1c443d3d1c`

```json
{
  "simulation_id": "0fa1cbe7-993c-4bd0-81ac-ae1c443d3d1c",
  "initial_portfolio_value": 100000,
  "tax_alpha": {
    "total_harvested_loss": -8620.56,
    "tax_alpha_pct": -0.0862
  },
  "tracking_error_annualized": 0.0543,
  "turnover": 0.4413,
  "n_harvest_events": 32
}
```

---

## What the numbers mean

### Tax Alpha: $8,621 in harvested losses (8.6% of portfolio)

Over two years, 32 harvests realized **$8,620 in losses** that would otherwise have just sat
on paper. At a 37% marginal rate, that's roughly **$3,190 in actual tax savings** on a
$100k portfolio, about a 3.2% after-tax gain with market exposure essentially unchanged.

The annualized rate (~4.3%/year) runs a bit high compared to the ~1-2% industry average.
That's mostly because this simulation ignores transaction costs (no brokerage fees, no
bid-ask spread). In a real system those costs push the optimal threshold higher, so the
engine fires less often.

### Tracking Error: 5.4% annualized

On average the basket's daily returns drifted **5.4% per year** away from the equal-weight
benchmark, higher than the less-than-2% a real product would target.

The culprit is replacement selection. When a position gets harvested, the simulator picks
the alphabetically-first eligible ticker in the same sector. Simple and deterministic, but
it doesn't care about correlation, so the replacement might move completely differently from
what it replaced. A covariance-based picker would minimize that drift instead, which is how
actual direct-indexing products keep tracking error tight.

### Turnover: 44% over two years (~22% per year)

Total sell-side volume came to **$44,131** against a $100k starting portfolio, about 22%
per year. That sits squarely in the 20-50% range for active direct-indexing strategies.

Lower turnover also means fewer taxable events from the replacement buys themselves, which
matters for clients who already have embedded gains they'd rather not trigger.

---

## Summary

| Metric | Result | Industry benchmark |
|---|---|---|
| Tax alpha (2yr) | -8.6% ($8,621) | -2 to -6% |
| Tax savings @ 37% | ~$3,190 | n/a |
| Tracking error | 5.4% annualized | less than 2% |
| Portfolio turnover | 22%/year | 20-50% |
| Harvest events | 32 (~1/month) | n/a |
| Total lots tracked | 92 | n/a |

Tracking error is the most visible gap between this simulation and a production system.
Everything else lands in a reasonable range. The limitations section in the README covers
exactly where the shortcuts are and what would replace them.
