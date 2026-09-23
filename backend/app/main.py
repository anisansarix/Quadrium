"""Quadrium — FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.database import close_duckdb, close_sqlite, get_duckdb, init_sqlite
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown hooks."""
    # --- Startup ---
    setup_logging()
    logger.info(
        "starting_quadrium",
        version=settings.version,
        environment=settings.env,
    )

    # Initialize databases
    await init_sqlite()
    logger.info("sqlite_initialized", path=settings.database.sqlite_path)

    get_duckdb()
    logger.info("duckdb_initialized", path=settings.database.duckdb_path)

    # Check GPU availability
    try:
        import torch

        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_mem = torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
            logger.info("gpu_detected", name=gpu_name, vram_mb=gpu_mem)
        else:
            logger.warning("no_gpu_detected", message="CUDA not available, using CPU")
    except ImportError:
        logger.warning("pytorch_not_installed", message="PyTorch not found")

    yield

    # --- Shutdown ---
    logger.info("shutting_down_quadrium")
    close_duckdb()
    await close_sqlite()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="Local-first AI/ML trading research platform",
        docs_url="/docs" if settings.api.docs_enabled else None,
        redoc_url="/redoc" if settings.api.docs_enabled else None,
        lifespan=lifespan,
    )

    # CORS for frontend dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routes
    from app.api.router import api_router

    app.include_router(api_router)

    return app


# Application instance for uvicorn
app = create_app()
