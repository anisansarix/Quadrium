from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.models import AccountState, Fill, Position


class MarketObservation(BaseModel):
    timestamp: datetime
    symbol: str
    features: dict[str, float]
    close_price: float  # Price at the exact moment of observation

class ActionProposal(BaseModel):
    symbol: str
    target_weight: float = Field(ge=-1.0, le=1.0)
    # Semantics:
    # -1.0 means 100% max short exposure allocation based on account equity
    # 0.0 means completely flat (0 exposure)
    # +1.0 means 100% max long exposure allocation based on account equity
    # This targets ABSOLUTE exposure, not a change in exposure.
    # The execution model will diff this against current exposure to generate trades.

class ExecutionRequest(BaseModel):
    symbol: str
    target_weight: float
    decision_time: datetime
    execution_time: datetime  # The time of the next available price

class PortfolioState(BaseModel):
    timestamp: datetime
    balance: float
    equity: float
    unrealized_pnl: float
    step_reward: float = 0.0
    positions: dict[str, Position]
    state: AccountState

class SimulatorStepResult(BaseModel):
    timestamp: datetime
    observation: MarketObservation | None
    portfolio: PortfolioState
    fills: list[Fill]
    realized_pnl: float
    step_reward: float = 0.0
    is_done: bool
    info: dict[str, Any]

