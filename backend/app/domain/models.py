from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"

class PositionState(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"

class AccountState(str, Enum):
    NORMAL = "NORMAL"
    FREEZE = "FREEZE"
    FLATTEN_AND_FREEZE = "FLATTEN_AND_FREEZE"

class RiskDecisionState(str, Enum):
    APPROVE = "APPROVE"
    CLAMP = "CLAMP"
    REJECT = "REJECT"
    FLATTEN = "FLATTEN"
    FREEZE = "FREEZE"

class JobState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class InstrumentSpec(BaseModel):
    broker_symbol: str
    canonical_symbol: str
    asset_class: str
    digits: int = Field(ge=0)
    point: float = Field(gt=0)
    tick_size: float = Field(gt=0)
    tick_value: float = Field(gt=0)
    contract_size: float = Field(gt=0)
    volume_min: float = Field(gt=0)
    volume_max: float = Field(gt=0)
    volume_step: float = Field(gt=0)
    margin_currency: str
    profit_currency: str
    execution_mode: str
    trading_sessions: dict[str, list[str]]
    stop_level: int = Field(ge=0)

    @model_validator(mode='after')
    def validate_volume(self) -> 'InstrumentSpec':
        if self.volume_min > self.volume_max:
            raise ValueError("volume_min must be <= volume_max")
        return self

class MarketBar(BaseModel):
    timestamp: datetime
    symbol: str
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    tick_volume: int = Field(ge=0)
    spread: int = Field(ge=0)
    real_volume: int = Field(ge=0)

class MarketTick(BaseModel):
    timestamp: datetime
    symbol: str
    bid: float = Field(gt=0)
    ask: float = Field(gt=0)
    last: float = Field(gt=0)
    volume: int = Field(ge=0)

class Quote(BaseModel):
    timestamp: datetime
    symbol: str
    bid: float = Field(gt=0)
    ask: float = Field(gt=0)

class AccountSnapshot(BaseModel):
    timestamp: datetime
    balance: float
    equity: float
    margin: float
    margin_free: float
    margin_level: float
    currency: str
    state: AccountState = AccountState.NORMAL

class Position(BaseModel):
    id: UUID
    symbol: str
    side: OrderSide
    volume: float = Field(gt=0)
    open_price: float = Field(gt=0)
    open_timestamp: datetime
    sl: float | None = None
    tp: float | None = None
    state: PositionState
    close_price: float | None = None
    close_timestamp: datetime | None = None
    pnl: float | None = None
    commission: float = 0.0
    swap: float = 0.0

class TargetPosition(BaseModel):
    symbol: str
    target_weight: float = Field(ge=-1.0, le=1.0) # -1.0 short max, 1.0 long max, 0 flat

class OrderIntent(BaseModel):
    symbol: str
    side: OrderSide
    type: OrderType
    volume: float = Field(gt=0)
    sl: float | None = None
    tp: float | None = None
    magic: int = 0
    comment: str = ""

class RiskPolicy(BaseModel):
    """
    Risk policy constraints mapping.
    
    Units and semantic implementation:
    - max_daily_loss_pct: float [0.0 - 1.0], implemented as FREEZE
    - max_drawdown_pct: float [0.0 - 1.0], implemented as FLATTEN
    - max_trade_risk_pct: float [0.0 - 1.0], implemented as REJECT
    - max_open_risk_pct: float [0.0 - 1.0], NOT IMPLEMENTED (TODO)
    - max_gross_exposure: float in account currency notional, implemented as REJECT (unless closing)
    - max_net_exposure: float in account currency notional, implemented as REJECT (unless closing)
    - max_position_count: int count of open positions, NOT IMPLEMENTED (TODO)
    - max_spread_pts: int in instrument points, implemented as REJECT
    - require_sl: bool, implemented as REJECT
    - session_constraints: dict, NOT IMPLEMENTED (TODO)
    - leverage_limit: float, multiplier of equity to gross notional, implemented as CLAMP
    
    The deterministic phase assumes a single USD account, single symbol, and USD profit currency.
    """
    id: str
    version: str
    max_daily_loss_pct: float
    max_drawdown_pct: float
    max_trade_risk_pct: float
    max_open_risk_pct: float
    max_gross_exposure: float
    max_net_exposure: float
    max_position_count: int
    max_spread_pts: int
    require_sl: bool
    session_constraints: dict[str, Any]
    leverage_limit: float

class RiskContext(BaseModel):
    account: AccountSnapshot
    open_positions: list[Position]
    current_quote: Quote
    instrument: InstrumentSpec
    start_of_day_equity: float
    equity_peak: float
    current_time: datetime

class RiskDecision(BaseModel):
    state: RiskDecisionState
    reasons: list[str] = []
    violations: list[str] = []
    proposed_target: float
    approved_target: float
    proposed_volume: float
    approved_volume: float
    policy_id: str
    policy_version: str
    timestamp: datetime

class ApprovedOrder(BaseModel):
    intent: OrderIntent
    risk_decision: RiskDecision
    timestamp: datetime

class Fill(BaseModel):
    order_id: str
    symbol: str
    volume: float
    price: float
    timestamp: datetime
    commission: float
    swap: float
    realized_pnl: float = 0.0

class ClosedTrade(BaseModel):
    trade_id: str
    symbol: str
    side: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    entry_volume: float
    exit_volume: float
    gross_pnl: float
    entry_commission: float
    exit_commission: float
    swap: float
    net_pnl: float
    holding_seconds: float
    exit_reason: str

class ExecutionResult(BaseModel):
    success: bool
    order_id: str | None = None
    error_message: str | None = None
    fills: list[Fill] = []
    closed_trades: list[ClosedTrade] = []

class DatasetManifest(BaseModel):
    source: str
    broker: str
    symbol: str
    timeframe: str
    timestamp_start: datetime
    timestamp_end: datetime
    row_count: int
    schema_version: str
    file_hash: str
    source_metadata: dict[str, Any]
    fetch_timestamp: datetime

class ExperimentSpec(BaseModel):
    git_sha: str
    dataset_hash: str
    feature_version: str
    simulator_version: str
    risk_policy_id: str
    risk_policy_version: str
    environment_version: str
    seed: int
    train_window: dict[str, datetime]
    validation_window: dict[str, datetime]
    test_window: dict[str, datetime]
    holdout_window: dict[str, datetime]
    execution_cost_profile: str

class ExperimentResult(BaseModel):
    experiment_id: str
    spec: ExperimentSpec
    hyperparameters: dict[str, Any]
    mlflow_run_id: str | None = None
    metrics: dict[str, Any] | None = None
    artifacts: list[str] = []

class SimulationEvent(BaseModel):
    timestamp: datetime
    fills: list[Fill] = []
    closed_trades: list[ClosedTrade] = []
    risk_events: list[RiskDecision] = []

class ExecutionRecord(BaseModel):
    order_id: str
    symbol: str
    side: str
    volume: float
    requested_price: float
    fill_price: float
    timestamp: datetime
    realized_pnl: float
    commission: float
    swap: float

class EquityRecord(BaseModel):
    timestamp: datetime
    balance: float
    equity: float
    floating_pnl: float
    realized_pnl_delta: float
    commission_delta: float
    swap_delta: float
    margin: float
    margin_free: float
    drawdown: float
    daily_pnl: float

class BacktestResult(BaseModel):
    experiment_result: ExperimentResult
    equity_curve: list[EquityRecord]
    closed_trades: list[ClosedTrade]
    executions: list[ExecutionRecord]
    risk_events: list[RiskDecision]
    metrics: dict[str, Any]
