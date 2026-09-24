import asyncio
from typing import Any

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.core.database import get_db_session
from app.core.logging import get_logger
from app.models.db import Job
from app.services.backtest_engine import BacktestEngine
from app.services.dataset_service import DatasetService

log = get_logger(__name__)

router = APIRouter(prefix="/backtest")

BACKTEST_SEMAPHORE = asyncio.Semaphore(2)


class StartBacktestRequest(BaseModel):
    experiment_id: str
    dataset_id: str
    agent_type: str = "ppo"
    model_path: str
    initial_balance: float = 10000.0
    instrument: str = "UNKNOWN"


async def run_backtest_job(job_id: str, request: StartBacktestRequest):
    async with BACKTEST_SEMAPHORE:
        async with get_db_session() as session:
            job = await session.get(Job, job_id)
            if not job:
                return
            job.status = "running"
            await session.commit()

        try:
            dataset_meta = DatasetService.get_dataset(request.dataset_id)
            df = pd.read_parquet(settings.resolve_path("data") / dataset_meta["file_path"])

            engine = BacktestEngine(
                experiment_id=request.experiment_id,
                df=df,
                agent_type=request.agent_type,
                model_path=request.model_path,
                initial_balance=request.initial_balance,
                instrument=request.instrument,
            )

            import anyio

            backtest_id = await anyio.to_thread.run_sync(engine.run)

            async with get_db_session() as session:
                job = await session.get(Job, job_id)
                if job:
                    job.status = "completed"
                    job.result = {"backtest_id": backtest_id}
                    await session.commit()

        except Exception as e:
            log.error("Backtest failed", job_id=job_id, error=str(e))
            async with get_db_session() as session:
                job = await session.get(Job, job_id)
                if job:
                    job.status = "failed"
                    job.error_message = str(e)
                    await session.commit()


from app.models.schemas import APIResponse


@router.post("/start", response_model=APIResponse)
async def start_backtest(request: StartBacktestRequest, background_tasks: BackgroundTasks) -> Any:
    """Start a new backtest job."""
    if BACKTEST_SEMAPHORE.locked():
        raise HTTPException(status_code=429, detail="Backtest capacity reached. Try again later.")

    async with get_db_session() as session:
        job = Job(job_type="backtest", experiment_id=request.experiment_id, status="queued")
        session.add(job)
        await session.flush()
        job_id = job.id

    background_tasks.add_task(run_backtest_job, job_id, request)
    return APIResponse(data={"job_id": job_id})


@router.get("/jobs/{job_id}", response_model=APIResponse)
async def get_job_status(job_id: str) -> Any:
    """Get status of a specific backtest job."""
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


from app.core.database import get_duckdb


@router.get("/{backtest_id}/trades", response_model=APIResponse)
def get_backtest_trades(backtest_id: str) -> Any:
    """Get all trades generated in a backtest."""
    conn = get_duckdb()
    result = conn.execute(
        "SELECT * FROM backtest_trades WHERE backtest_id = ?", [backtest_id]
    ).fetchdf()
    if not result.empty:
        result["entry_time"] = result["entry_time"].astype(str)
        result["exit_time"] = result["exit_time"].astype(str)
    return APIResponse(data=result.to_dict(orient="records"))


@router.get("/{backtest_id}/metrics", response_model=APIResponse)
def get_backtest_metrics(backtest_id: str) -> Any:
    """Get aggregated metrics for a backtest."""
    conn = get_duckdb()
    result = conn.execute(
        "SELECT * FROM backtest_metrics WHERE backtest_id = ?", [backtest_id]
    ).fetchdf()
    if result.empty:
        raise HTTPException(status_code=404, detail="Metrics not found")
    return APIResponse(data=result.to_dict(orient="records")[0])
