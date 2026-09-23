from typing import Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.pine_generator import generate_pine_script

router = APIRouter(prefix="/strategies", tags=["Strategies"])

class GeneratePineRequest(BaseModel):
    experiment_id: str
    params: dict[str, Any]

@router.post("/generate/pine")
def generate_pine(request: GeneratePineRequest) -> dict[str, Any]:
    try:
        script = generate_pine_script(request.experiment_id, request.params)
        return {"success": True, "data": {"script": script}, "error": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
