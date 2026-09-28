from enum import Enum
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4

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
    digits: int
    point: float
    tick_size: float
    tick_value: float
    contract_size: float
    volume_min: float
    volume_max: float
    volume_step: float
    margin_currency: str
    profit_currency: str
    execution_mode: str
    trading_sessions: Dict[str, List[str]]
    stop_level: int

class MarketBar(BaseModel):
    timestamp: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    spread: int
    real_volume: int

class MarketTick(BaseModel):
    timestamp: datetime
    symbol: str
    bid: float
    ask: float
    last: float
    volume: int

class Quote(BaseModel):
    timestamp: datetime
    symbol: str
    bid: float
    ask: float

class AccountSnapshot(BaseModel):
    timestamp: datetime
    balance: float
    equity: float
    margin: float
    margin_free: float
    margin_level: float
    currency: str

class Position(BaseModel):
    id: UUID
    symbol: str
    side: OrderSide
    volume: float
    open_price: float
    open_timestamp: datetime
    sl: Optional[float] = None
    tp: Optional[float] = None
    state: PositionState
    close_price: Optional[float] = None
    close_timestamp: Optional[datetime] = None
    pnl: Optional[float] = None

class OrderIntent(BaseModel):
    symbol: str
    side: OrderSide
    type: OrderType
    volume: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    magic: int = 0
    comment: str = ""

class TargetPosition(BaseModel):
    symbol: str
    target_volume: float  # Positive for long, negative for short, 0 for flat

class RiskPolicy(BaseModel):
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
    session_constraints: Dict[str, Any]
    leverage_limit: float

class RiskContext(BaseModel):
    account: AccountSnapshot
    open_positions: List[Position]
    current_quote: Quote
    instrument: InstrumentSpec

class RiskDecision(BaseModel):
    state: RiskDecisionState
    reason: str = ""
    clamped_volume: Optional[float] = None

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

class ExecutionResult(BaseModel):
    success: bool
    order_id: Optional[str] = None
    error_message: Optional[str] = None
    fill: Optional[Fill] = None

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
    source_metadata: Dict[str, Any]
    fetch_timestamp: datetime

class ExperimentManifest(BaseModel):
    experiment_id: str
    git_sha: str
    dataset_hash: str
    feature_version: str
    simulator_version: str
    risk_policy_id: str
    risk_policy_version: str
    environment_version: str
    seed: int
    hyperparameters: Dict[str, Any]
    train_window: Dict[str, datetime]
    validation_window: Dict[str, datetime]
    test_window: Dict[str, datetime]
    holdout_window: Dict[str, datetime]
    execution_cost_profile: str
    mlflow_run_id: str
    metrics: Dict[str, Any]
    artifacts: List[str]
