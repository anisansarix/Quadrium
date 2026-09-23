import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.core.logging import get_logger
from app.ml.training.trainer import Trainer
from app.services.dataset_service import DatasetService

log = get_logger(__name__)

router = APIRouter(prefix="/training")

# In-memory store for tracking jobs (in production, use SQLite job table)
_active_jobs = {}

class StartTrainingRequest(BaseModel):
    dataset_id: str
    experiment_id: str
    agent_type: str = "ppo"
    hyperparameters: dict | None = None
    total_timesteps: int = 10000

def run_training_job(job_id: str, request: StartTrainingRequest):
    """Background task for training."""
    try:
        _active_jobs[job_id]["status"] = "training"

        # Load dataset
        dataset_meta = DatasetService.get_dataset(request.dataset_id)
        import pandas as pd

        from app.config import settings

        df = pd.read_parquet(settings.resolve_path("data") / dataset_meta["file_path"])

        trainer = Trainer(
            experiment_id=request.experiment_id,
            df=df,
            agent_type=request.agent_type,
            hyperparams=request.hyperparameters
        )

        run_id = trainer.train(total_timesteps=request.total_timesteps)

        _active_jobs[job_id]["status"] = "completed"
        _active_jobs[job_id]["run_id"] = run_id

    except Exception as e:
        log.error("Training job failed", job_id=job_id, error=str(e))
        _active_jobs[job_id]["status"] = "failed"
        _active_jobs[job_id]["error"] = str(e)

@router.post("/start")
async def start_training(request: StartTrainingRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Start a new training job."""
    job_id = str(uuid.uuid4())
    _active_jobs[job_id] = {
        "id": job_id,
        "experiment_id": request.experiment_id,
        "status": "queued"
    }

    background_tasks.add_task(run_training_job, job_id, request)
    return {"success": True, "data": {"job_id": job_id}, "error": None}

@router.get("/jobs")
async def list_jobs() -> dict[str, Any]:
    """List active and completed training jobs."""
    return {"success": True, "data": list(_active_jobs.values()), "error": None}

@router.get("/{job_id}/status")
async def get_job_status(job_id: str) -> dict[str, Any]:
    """Get status of a specific training job."""
    if job_id not in _active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True, "data": _active_jobs[job_id], "error": None}
