from typing import Any

from fastapi import APIRouter

from app.services.feature_service import FeatureService

router = APIRouter(prefix="/features")

@router.get("")
async def list_available_features() -> dict[str, Any]:
    """List all available features that can be applied to datasets."""
    features = FeatureService.get_available_features()
    return {"success": True, "data": features, "error": None}
