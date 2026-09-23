from decimal import Decimal
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.logging import get_logger
from app.services.risk_engine import RiskEngine

log = get_logger(__name__)

router = APIRouter(prefix="/risk")

class CalculateRiskRequest(BaseModel):
    # For ad-hoc risk calculation. In reality, we'd accept trade JSON.
    equity_curve: list[float]
    initial_balance: float = 10000.0
    # trades: list[dict] = [] # Too complex for basic schema, omitting for now

@router.post("/calculate")
async def calculate_risk(request: CalculateRiskRequest) -> dict[str, Any]:
    """Calculate risk metrics for an ad-hoc equity curve."""
    try:
        curve = np.array(request.equity_curve)

        dd = RiskEngine.max_drawdown(curve)
        trailing_dd = RiskEngine.drawdown_trailing(curve, Decimal(str(request.initial_balance)))

        return {
            "success": True,
            "data": {
                "max_drawdown_abs": float(dd.max_drawdown_abs),
                "max_drawdown_pct": float(dd.max_drawdown_pct),
                "trailing_drawdown_abs": float(trailing_dd.max_drawdown_abs),
                "trailing_drawdown_pct": float(trailing_dd.max_drawdown_pct),
            },
            "error": None
        }
    except Exception as e:
        log.error("Failed to calculate risk", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{experiment_id}")
async def get_experiment_risk(experiment_id: str) -> dict[str, Any]:
    """Get full risk metrics for an experiment's backtests."""
    # Placeholder for DuckDB fetching of experiment backtest metrics
    return {
        "success": True,
        "data": {
            "experiment_id": experiment_id,
            "metrics": "Not fully implemented until Backtest integration"
        },
        "error": None
    }
