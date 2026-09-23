"""System endpoints — health checks, GPU status, dashboard summary."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.models.schemas import APIResponse, GPUStatus, HealthResponse

router = APIRouter(prefix="/system")


@router.get("/health", response_model=APIResponse[HealthResponse])
async def health_check() -> APIResponse[HealthResponse]:
    """Application health check with component status."""
    gpu_available = False
    gpu_name = None
    gpu_memory_mb = None

    try:
        import torch

        gpu_available = torch.cuda.is_available()
        if gpu_available:
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory_mb = int(torch.cuda.get_device_properties(0).total_memory / (1024 * 1024))
    except ImportError:
        pass

    # Check SQLite
    sqlite_ok = True
    try:
        from app.core.database import get_engine

        engine = get_engine()
        sqlite_ok = engine is not None
    except Exception:
        sqlite_ok = False

    # Check DuckDB
    duckdb_ok = True
    try:
        from app.core.database import get_duckdb

        conn = get_duckdb()
        conn.execute("SELECT 1")
        duckdb_ok = True
    except Exception:
        duckdb_ok = False

    return APIResponse(
        data=HealthResponse(
            status="ok",
            version=settings.version,
            environment=settings.env,
            gpu_available=gpu_available,
            gpu_name=gpu_name,
            gpu_memory_mb=gpu_memory_mb,
            sqlite_connected=sqlite_ok,
            duckdb_connected=duckdb_ok,
        )
    )


@router.get("/gpu", response_model=APIResponse[GPUStatus])
async def gpu_status() -> APIResponse[GPUStatus]:
    """Detailed GPU/CUDA status."""
    try:
        import torch

        cuda_available = torch.cuda.is_available()
        return APIResponse(
            data=GPUStatus(
                cuda_available=cuda_available,
                device_name=torch.cuda.get_device_name(0) if cuda_available else None,
                device_count=torch.cuda.device_count() if cuda_available else 0,
                dedicated_memory_mb=(
                    int(torch.cuda.get_device_properties(0).total_memory / (1024 * 1024))
                    if cuda_available
                    else None
                ),
                cuda_version=torch.version.cuda if cuda_available else None,
                pytorch_version=torch.__version__,
            )
        )
    except ImportError:
        return APIResponse(
            data=GPUStatus(cuda_available=False),
            error="PyTorch not installed",
        )
