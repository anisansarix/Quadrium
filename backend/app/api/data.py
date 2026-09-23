from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.exceptions import DataError
from app.models.schemas import APIResponse
from app.services.data_service import DataService

router = APIRouter(prefix="/data", tags=["data"])


class FetchDataRequest(BaseModel):
    symbol: str
    timeframe: str
    start: datetime
    end: datetime
    source: str = "mt5"


@router.post("/fetch", response_model=APIResponse)
async def fetch_historical_data(request: FetchDataRequest) -> Any:
    """
    Fetch historical market data from MT5 or Yahoo Finance and store it in Parquet format.
    """
    try:
        catalog_id = await DataService.fetch_and_store(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start=request.start,
            end=request.end,
            source=request.source,
        )
        return APIResponse(data={"catalog_id": catalog_id, "status": "success"})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DataError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")


@router.get("/raw", response_model=APIResponse)
def list_raw_data(instrument: str | None = Query(None, description="Filter by instrument")) -> Any:
    """
    List all cataloged raw market data.
    """
    try:
        data = DataService.list_raw_data(instrument=instrument)
        return APIResponse(data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")
