"""Tests for the system API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """Health endpoint returns OK status with component info."""
    response = await client.get("/api/system/health")
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["data"]["version"] == "0.1.0"
    assert "gpu_available" in body["data"]
    assert "sqlite_connected" in body["data"]
    assert "duckdb_connected" in body["data"]


@pytest.mark.asyncio
async def test_gpu_status(client: AsyncClient) -> None:
    """GPU endpoint returns CUDA availability info."""
    response = await client.get("/api/system/gpu")
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    assert "cuda_available" in body["data"]
