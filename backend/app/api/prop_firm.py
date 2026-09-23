from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.services.prop_firm import PropFirmSimulator
from app.core.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/prop-firm")

@router.get("/profiles")
async def list_profiles() -> dict[str, Any]:
    """List available prop firm profiles."""
    try:
        profiles_dir = settings.resolve_path("config/prop_firms")
        profiles = PropFirmSimulator.load_profiles_from_dir(profiles_dir)
        # Convert to dicts for API response
        profiles_list = []
        for pid, p in profiles.items():
            profiles_list.append({
                "id": pid,
                "name": p.name,
                "account_size": float(p.account_size),
                "max_overall_drawdown_pct": float(p.max_overall_drawdown_pct),
                "max_daily_loss_pct": float(p.max_daily_loss_pct)
            })
        return {"success": True, "data": profiles_list, "error": None}
    except Exception as e:
        log.error("Failed to list profiles", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

class SimulateRequest(BaseModel):
    profile_id: str
    experiment_id: str
    # In a real system, we fetch trades and equity from DB using experiment_id

@router.post("/simulate")
async def simulate(request: SimulateRequest) -> dict[str, Any]:
    """Run prop firm challenge simulation."""
    # Placeholder for actual trade fetch
    return {
        "success": True, 
        "data": {
            "status": "in_progress",
            "detail": "Integration with backtest trades pending."
        },
        "error": None
    }
