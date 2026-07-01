import sqlite3
from datetime import date

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException

from pave.api.deps import get_db
from pave.api.schemas import (
    BasketResponse,
    ConstructRequest,
    EvaluateResponse,
    SimulateRequest,
    SimulateResponse,
    TaxAlphaResult,
)
from pave.evaluation.metrics import compute_tax_alpha, compute_tracking_error, compute_turnover
from pave.harvesting.simulate import run_simulation
from pave.pipeline.store import load_harvest_events, load_lots, load_prices, load_securities
from pave.portfolio.benchmark import compute_benchmark_weights
from pave.portfolio.construct import construct_basket

app = FastAPI(
    title="Pave TLH Simulator",
    description="Direct indexing + tax-loss harvesting simulation API",
    version="0.1.0",
)


@app.post("/portfolio/construct", response_model=BasketResponse)
def construct(req: ConstructRequest, conn: sqlite3.Connection = Depends(get_db)):
    securities = load_securities(conn)
    if securities.empty:
        raise HTTPException(status_code=503, detail="No securities in DB — run the pipeline first.")

    benchmark_weights = compute_benchmark_weights(securities)

    try:
        basket = construct_basket(
            benchmark_weights,
            securities,
            n_stocks=req.n_stocks,
            excluded_sectors=req.excluded_sectors or None,
            max_weight_per_position=req.max_weight_per_position,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return BasketResponse(
        basket=basket.to_dict(),
        n_positions=len(basket),
        sectors_excluded=req.excluded_sectors,
    )


@app.post("/simulate/harvest", response_model=SimulateResponse)
def simulate(req: SimulateRequest, conn: sqlite3.Connection = Depends(get_db)):
    start = date.fromisoformat(req.start_date)
    end = date.fromisoformat(req.end_date)
    tickers = list(req.basket.keys())

    securities = load_securities(conn)
    prices_df = load_prices(conn, tickers, start, end)

    if len(prices_df["date"].unique()) < 2:
        raise HTTPException(
            status_code=422,
            detail=f"Not enough price data for {tickers} between {start} and {end}. "
                   "Run the pipeline to populate prices first.",
        )

    basket = pd.Series(req.basket)

    sim_id = run_simulation(
        conn=conn,
        basket=basket,
        prices_df=prices_df,
        securities=securities,
        initial_portfolio_value=req.initial_portfolio_value,
        harvest_threshold=req.harvest_threshold,
    )

    lots = load_lots(conn, sim_id)
    events = load_harvest_events(conn, sim_id)

    return SimulateResponse(
        simulation_id=sim_id,
        n_lots=len(lots),
        n_harvest_events=len(events),
    )


@app.get("/evaluate/{simulation_id}", response_model=EvaluateResponse)
def evaluate(
    simulation_id: str,
    initial_portfolio_value: float = 100_000.0,
    conn: sqlite3.Connection = Depends(get_db),
):
    lots_df = load_lots(conn, simulation_id)
    if lots_df.empty:
        raise HTTPException(status_code=404, detail=f"Simulation {simulation_id!r} not found.")

    events_df = load_harvest_events(conn, simulation_id)

    # recover basket weights from the initial purchase lots (first trading day)
    first_date = lots_df["purchase_date"].min()
    initial_lots = lots_df[lots_df["purchase_date"] == first_date].copy()
    initial_lots["value"] = initial_lots["quantity"] * initial_lots["cost_basis_per_share"]
    total_value = initial_lots["value"].sum()
    basket_weights = (
        initial_lots.groupby("ticker")["value"].sum() / total_value
    )

    tickers = lots_df["ticker"].unique().tolist()
    securities = load_securities(conn)
    prices_df = load_prices(conn, tickers, date.fromisoformat(first_date), date.today())
    benchmark_weights = compute_benchmark_weights(securities)

    tax_alpha = compute_tax_alpha(events_df, initial_portfolio_value)
    turnover = compute_turnover(events_df, initial_portfolio_value)

    try:
        te = compute_tracking_error(prices_df, basket_weights, benchmark_weights)
    except ValueError:
        te = 0.0  # not enough price data to compute — return 0 rather than 500

    return EvaluateResponse(
        simulation_id=simulation_id,
        initial_portfolio_value=initial_portfolio_value,
        tax_alpha=TaxAlphaResult(**tax_alpha),
        tracking_error_annualized=te,
        turnover=turnover,
        n_harvest_events=len(events_df),
    )
