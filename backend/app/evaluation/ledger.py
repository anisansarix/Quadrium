

from app.domain.models import ClosedTrade, EquityRecord, ExecutionRecord


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
