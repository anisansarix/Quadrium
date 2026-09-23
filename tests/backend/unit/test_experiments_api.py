"""Tests for experiment CRUD endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_experiment(client: AsyncClient) -> None:
    """Create an experiment and verify response."""
    response = await client.post(
        "/api/experiments",
        json={
            "name": "XAUUSD PPO Test",
            "instrument": "XAUUSD",
            "timeframe": "H1",
            "agent_type": "ppo",
            "random_seed": 42,
            "notes": "Initial test experiment",
        },
    )
    assert response.status_code == 201

    body = response.json()
    assert body["success"] is True
    assert body["data"]["name"] == "XAUUSD PPO Test"
    assert body["data"]["instrument"] == "XAUUSD"
    assert body["data"]["timeframe"] == "H1"
    assert body["data"]["agent_type"] == "ppo"
    assert body["data"]["status"] == "created"
    assert body["data"]["id"] is not None


@pytest.mark.asyncio
async def test_list_experiments_empty(client: AsyncClient) -> None:
    """List experiments returns empty list initially."""
    response = await client.get("/api/experiments")
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)
    assert body["pagination"] is not None


@pytest.mark.asyncio
async def test_get_experiment_not_found(client: AsyncClient) -> None:
    """Requesting a non-existent experiment returns 404."""
    response = await client.get("/api/experiments/nonexistent-id")
    assert response.status_code == 404
