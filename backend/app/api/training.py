import asyncio
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.core.database import get_db_session
from app.core.logging import get_logger
from app.ml.training.trainer import Trainer
from app.models.db import Job
from app.services.dataset_service import DatasetService

log = get_logger(__name__)

router = APIRouter(prefix="/training")

TRAINING_SEMAPHORE = asyncio.Semaphore(1)


class StartTrainingRequest(BaseModel):
    dataset_id: str
    experiment_id: str
    agent_type: str = "ppo"
    hyperparameters: dict | None = None
    total_timesteps: int = 10000


async def run_training_job(job_id: str, request: StartTrainingRequest):
    """Background task for training."""
    async with TRAINING_SEMAPHORE:
        async with get_db_session() as session:
            job = await session.get(Job, job_id)
            if not job:
                return
            job.status = "training"
            await session.commit()

        try:
            # Load dataset
            dataset_meta = DatasetService.get_dataset(request.dataset_id)
            import pandas as pd

            from app.config import settings

            df = pd.read_parquet(settings.resolve_path("data") / dataset_meta["file_path"])

            trainer = Trainer(
                experiment_id=request.experiment_id,
                df=df,
                agent_type=request.agent_type,
                hyperparams=request.hyperparameters,
            )

            import anyio

            run_id = await anyio.to_thread.run_sync(trainer.train, request.total_timesteps)

            async with get_db_session() as session:
                job = await session.get(Job, job_id)
                if job:
                    job.status = "completed"
                    job.result = {"run_id": run_id}
                    await session.commit()

        except Exception as e:
            log.error("Training job failed", job_id=job_id, error=str(e))
            async with get_db_session() as session:
                job = await session.get(Job, job_id)
                if job:
                    job.status = "failed"
                    job.error_message = str(e)
                    await session.commit()


from app.models.schemas import APIResponse


@router.post("/start", response_model=APIResponse)
async def start_training(request: StartTrainingRequest, background_tasks: BackgroundTasks) -> Any:
    """Start a new training job."""
    if TRAINING_SEMAPHORE.locked():
        raise HTTPException(status_code=429, detail="Training capacity reached. Try again later.")

    async with get_db_session() as session:
        job = Job(job_type="training", experiment_id=request.experiment_id, status="queued")
        session.add(job)
        await session.flush()
        job_id = job.id

    background_tasks.add_task(run_training_job, job_id, request)
    return APIResponse(data={"job_id": job_id})


@router.get("/jobs", response_model=APIResponse)
async def list_jobs() -> Any:
    """List active and completed training jobs."""
    async with get_db_session() as session:
        result = await session.execute(select(Job).where(Job.job_type == "training"))
        jobs = result.scalars().all()
        return APIResponse(
            data=[{"id": j.id, "status": j.status, "experiment_id": j.experiment_id} for j in jobs]
        )


@router.get("/{job_id}/status", response_model=APIResponse)
async def get_job_status(job_id: str) -> Any:
    """Get status of a specific training job."""
    async with get_db_session() as session:
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return APIResponse(
            data={
                "id": job.id,
                "status": job.status,
                "error": job.error_message,
                "result": job.result,
            }
        )
