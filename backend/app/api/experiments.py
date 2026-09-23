"""Experiment CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.core.database import get_db_session
from app.models.db import Experiment
from app.models.schemas import (
    APIResponse,
    ExperimentCreate,
    ExperimentResponse,
    ExperimentUpdate,
    PaginationInfo,
)

router = APIRouter(prefix="/experiments")


def _experiment_to_response(exp: Experiment) -> ExperimentResponse:
    """Convert ORM model to Pydantic response."""
    return ExperimentResponse(
        id=exp.id,
        name=exp.name,
        status=exp.status,
        instrument=exp.instrument,
        timeframe=exp.timeframe,
        agent_type=exp.agent_type,
        dataset_version=exp.dataset_version,
        hyperparameters=exp.hyperparameters,
        reward_function=exp.reward_function,
        random_seed=exp.random_seed,
        training_config=exp.training_config,
        risk_config=exp.risk_config,
        prop_firm_profile=exp.prop_firm_profile,
        environment_config=exp.environment_config,
        hardware_info=exp.hardware_info,
        mlflow_run_id=exp.mlflow_run_id,
        metrics=exp.metrics,
        notes=exp.notes,
        created_at=exp.created_at,
        started_at=exp.started_at,
        completed_at=exp.completed_at,
    )


@router.get("", response_model=APIResponse[list[ExperimentResponse]])
async def list_experiments(
    page: int = 1,
    page_size: int = 50,
    status: str | None = None,
    instrument: str | None = None,
) -> APIResponse[list[ExperimentResponse]]:
    """List experiments with optional filtering."""
    async with get_db_session() as session:
        query = select(Experiment).order_by(Experiment.created_at.desc())

        if status:
            query = query.where(Experiment.status == status)
        if instrument:
            query = query.where(Experiment.instrument == instrument)

        # Count total
        from sqlalchemy import func

        count_query = select(func.count()).select_from(query.subquery())
        total = (await session.execute(count_query)).scalar_one()

        # Paginate
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        result = await session.execute(query)
        experiments = result.scalars().all()

        return APIResponse(
            data=[_experiment_to_response(exp) for exp in experiments],
            pagination=PaginationInfo(page=page, page_size=page_size, total=total),
        )


@router.post("", response_model=APIResponse[ExperimentResponse], status_code=201)
async def create_experiment(body: ExperimentCreate) -> APIResponse[ExperimentResponse]:
    """Create a new experiment."""
    async with get_db_session() as session:
        experiment = Experiment(
            name=body.name,
            instrument=body.instrument,
            timeframe=body.timeframe,
            agent_type=body.agent_type,
            dataset_version=body.dataset_version,
            hyperparameters=body.hyperparameters,
            reward_function=body.reward_function,
            random_seed=body.random_seed,
            training_config=body.training_config,
            risk_config=body.risk_config,
            prop_firm_profile=body.prop_firm_profile,
            environment_config=body.environment_config,
            notes=body.notes,
        )
        session.add(experiment)
        await session.flush()
        await session.refresh(experiment)
        return APIResponse(data=_experiment_to_response(experiment))


@router.get("/{experiment_id}", response_model=APIResponse[ExperimentResponse])
async def get_experiment(experiment_id: str) -> APIResponse[ExperimentResponse]:
    """Get a single experiment by ID."""
    async with get_db_session() as session:
        result = await session.execute(
            select(Experiment).where(Experiment.id == experiment_id)
        )
        experiment = result.scalar_one_or_none()
        if experiment is None:
            raise HTTPException(status_code=404, detail="Experiment not found")
        return APIResponse(data=_experiment_to_response(experiment))


@router.put("/{experiment_id}", response_model=APIResponse[ExperimentResponse])
async def update_experiment(
    experiment_id: str, body: ExperimentUpdate
) -> APIResponse[ExperimentResponse]:
    """Update an experiment (partial)."""
    async with get_db_session() as session:
        result = await session.execute(
            select(Experiment).where(Experiment.id == experiment_id)
        )
        experiment = result.scalar_one_or_none()
        if experiment is None:
            raise HTTPException(status_code=404, detail="Experiment not found")

        update_data = body.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(experiment, key, value)

        await session.flush()
        await session.refresh(experiment)
        return APIResponse(data=_experiment_to_response(experiment))


@router.delete("/{experiment_id}", response_model=APIResponse[None])
async def delete_experiment(experiment_id: str) -> APIResponse[None]:
    """Delete an experiment."""
    async with get_db_session() as session:
        result = await session.execute(
            select(Experiment).where(Experiment.id == experiment_id)
        )
        experiment = result.scalar_one_or_none()
        if experiment is None:
            raise HTTPException(status_code=404, detail="Experiment not found")

        await session.delete(experiment)
        return APIResponse(success=True)
