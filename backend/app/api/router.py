"""Root API router — aggregates all endpoint modules."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.backtest import router as backtest_router
from app.api.data import router as data_router
from app.api.datasets import router as datasets_router
from app.api.experiments import router as experiments_router
from app.api.features import router as features_router
from app.api.prop_firm import router as prop_firm_router
from app.api.risk import router as risk_router
from app.api.system import router as system_router
from app.api.training import router as training_router
from app.api.live_trading import router as live_trading_router

api_router = APIRouter(prefix="/api")

from app.api.mt5 import router as mt5_router
from app.api.strategies import router as strategies_router
from app.config import settings

# Register sub-routers
api_router.include_router(system_router, tags=["System"])
api_router.include_router(experiments_router, tags=["Experiments"])
api_router.include_router(data_router, tags=["Market Data"])
api_router.include_router(datasets_router, tags=["Datasets"])
api_router.include_router(features_router, tags=["Features"])
api_router.include_router(training_router, tags=["Training"])
api_router.include_router(risk_router, tags=["Risk"])
api_router.include_router(prop_firm_router, tags=["Prop Firm"])
api_router.include_router(backtest_router, tags=["Backtesting"])
api_router.include_router(live_trading_router)

if settings.mt5.enabled:
    api_router.include_router(mt5_router, tags=["MT5"])

api_router.include_router(strategies_router, tags=["Strategies"])
