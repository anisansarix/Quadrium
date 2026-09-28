from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TradeRecord(BaseModel):
    id: UUID
    timestamp: datetime
    symbol: str
    side: str
    volume: float
    requested_price: float
    fill_price: float
    sl: float | None = None
    tp: float | None = None
    commission: float
    swap: float
    realized_pnl: float
    unrealized_pnl: float
    balance: float
    equity: float
    drawdown: float
    risk_decision: str
    risk_policy_version: str

class Ledger:
    def __init__(self):
        self.trades: list[TradeRecord] = []

    def append(self, record: TradeRecord):
        self.trades.append(record)

    def to_dataframe(self):
        import pandas as pd
        if not self.trades:
            return pd.DataFrame()
        return pd.DataFrame([t.model_dump() for t in self.trades])
