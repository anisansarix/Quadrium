from typing import Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import uuid

from app.core.logging import get_logger
from app.services.backtest_engine import BacktestEngine
from app.services.dataset_service import DatasetService
from app.config import settings
import pandas as pd

log = get_logger(__name__)

router = APIRouter(prefix="/backtest")

_active_backtests = {}

class StartBacktestRequest(BaseModel):
    experiment_id: str
    dataset_id: str
    agent_type: str = "ppo"
    model_path: str
    initial_balance: float = 10000.0
    instrument: str = "UNKNOWN"

def run_backtest_job(job_id: str, request: StartBacktestRequest):
    try:
        _active_backtests[job_id]["status"] = "running"
        
        dataset_meta = DatasetService.get_dataset(request.dataset_id)
        df = pd.read_parquet(settings.resolve_path("data") / dataset_meta["file_path"])
        
        engine = BacktestEngine(
            experiment_id=request.experiment_id,
            df=df,
            agent_type=request.agent_type,
            model_path=request.model_path,
            initial_balance=request.initial_balance,
            instrument=request.instrument
        )
        
        backtest_id = engine.run()
        
        _active_backtests[job_id]["status"] = "completed"
        _active_backtests[job_id]["backtest_id"] = backtest_id
        
    except Exception as e:
        log.error("Backtest failed", job_id=job_id, error=str(e))
        _active_backtests[job_id]["status"] = "failed"
        _active_backtests[job_id]["error"] = str(e)

@router.post("/start")
async def start_backtest(request: StartBacktestRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Start a new backtest job."""
    job_id = str(uuid.uuid4())
    _active_backtests[job_id] = {
        "id": job_id,
        "experiment_id": request.experiment_id,
        "status": "queued"
    }
    
    background_tasks.add_task(run_backtest_job, job_id, request)
    return {"success": True, "data": {"job_id": job_id}, "error": None}

@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str) -> dict[str, Any]:
    """Get status of a specific backtest job."""
    if job_id not in _active_backtests:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True, "data": _active_backtests[job_id], "error": None}
