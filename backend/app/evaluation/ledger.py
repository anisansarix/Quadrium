from datetime import datetime

from pydantic import BaseModel

from app.domain.models import ClosedTrade


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

class Ledger:
    def __init__(self):
        self.executions: list[ExecutionRecord] = []
        self.closed_trades: list[ClosedTrade] = []
        self.equity_curve: list[EquityRecord] = []

    def append_execution(self, record: ExecutionRecord):
        self.executions.append(record)

    def append_closed_trade(self, record: ClosedTrade):
        self.closed_trades.append(record)
        
    def append_equity_record(self, record: EquityRecord):
        self.equity_curve.append(record)
