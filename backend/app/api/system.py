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


import os


@router.get("/logs", response_model=APIResponse[list[str]])
async def get_system_logs() -> APIResponse[list[str]]:
    """Get recent system logs."""
    log_file = "quadrium.log"
    if not os.path.exists(log_file):
        return APIResponse(data=[])

    try:
        with open(log_file) as f:
            lines = f.readlines()
            # Return last 50 lines
            return APIResponse(data=[line.strip() for line in lines[-50:]])
    except Exception as e:
        return APIResponse(data=[], error=str(e))


@router.delete("/logs", response_model=APIResponse[dict])
async def clear_system_logs() -> APIResponse[dict]:
    """Clear the system logs."""
    log_file = "quadrium.log"
    try:
        if os.path.exists(log_file):
            open(log_file, "w").close()
        return APIResponse(data={"status": "cleared"})
    except Exception as e:
        return APIResponse(data={"status": "error"}, error=str(e))
