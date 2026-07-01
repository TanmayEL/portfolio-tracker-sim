from pydantic import BaseModel


class ConstructRequest(BaseModel):
    n_stocks: int = 30
    excluded_sectors: list[str] = []
    max_weight_per_position: float | None = None


class BasketResponse(BaseModel):
    basket: dict[str, float]
    n_positions: int
    sectors_excluded: list[str]


class SimulateRequest(BaseModel):
    basket: dict[str, float]
    initial_portfolio_value: float = 100_000.0
    harvest_threshold: float = 0.05
    start_date: str = "2023-01-01"
    end_date: str = "2024-12-31"


class SimulateResponse(BaseModel):
    simulation_id: str
    n_lots: int
    n_harvest_events: int


class TaxAlphaResult(BaseModel):
    total_harvested_loss: float
    tax_alpha_pct: float


class EvaluateResponse(BaseModel):
    simulation_id: str
    initial_portfolio_value: float
    tax_alpha: TaxAlphaResult
    tracking_error_annualized: float
    turnover: float
    n_harvest_events: int
