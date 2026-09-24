from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.exceptions import DataError
from app.core.logging import get_logger
from app.services.dataset_service import DatasetService

log = get_logger(__name__)

router = APIRouter(prefix="/datasets")

class CreateDatasetRequest(BaseModel):
    raw_data_id: str
    version: str
    features: list[str]

from app.models.schemas import APIResponse

@router.post("", status_code=status.HTTP_201_CREATED, response_model=APIResponse)
async def create_dataset(request: CreateDatasetRequest) -> Any:
    """Create a new processed dataset from a raw dataset by applying features."""
    try:
        dataset_id = DatasetService.create_dataset(
            raw_data_id=request.raw_data_id,
            version=request.version,
            features=request.features
        )
        return APIResponse(data={"dataset_id": dataset_id})
    except DataError as e:
        log.warning("Dataset creation failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error("Internal error during dataset creation", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("", response_model=APIResponse)
async def list_datasets(instrument: str | None = None) -> Any:
    """List all processed datasets."""
    try:
        datasets = DatasetService.list_datasets(instrument=instrument)
        return APIResponse(data=datasets)
    except Exception as e:
        log.error("Failed to list datasets", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/{dataset_id}", response_model=APIResponse)
async def get_dataset(dataset_id: str) -> Any:
    """Get metadata for a specific dataset."""
    try:
        dataset = DatasetService.get_dataset(dataset_id)
        return APIResponse(data=dataset)
    except DataError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        log.error("Failed to get dataset", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")
