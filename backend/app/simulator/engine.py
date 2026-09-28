from typing import List, Dict, Optional
from datetime import datetime
from uuid import uuid4
from app.domain.models import ApprovedOrder, ExecutionResult, Position, AccountSnapshot, Quote, InstrumentSpec, PositionState, OrderSide, Fill

class SimulatorEngine:
    def __init__(self, initial_balance: float = 10000.0, currency: str = "USD"):
        self.balance = initial_balance
        self.equity = initial_balance
        self.margin = 0.0
        self.currency = currency
        self.positions: List[Position] = []
        self.current_time: Optional[datetime] = None
        self.quotes: Dict[str, Quote] = {}
        self.instruments: Dict[str, InstrumentSpec] = {}
        
    def set_instrument(self, spec: InstrumentSpec):
        self.instruments[spec.canonical_symbol] = spec

    def update_quote(self, quote: Quote):
        self.quotes[quote.symbol] = quote
        self.current_time = quote.timestamp
        self._update_equity()

    def _update_equity(self):
        # A simple deterministic accounting update
        unrealized_pnl = 0.0
        for p in self.positions:
            if p.state == PositionState.OPEN:
                q = self.quotes.get(p.symbol)
                if q:
                    if p.side == OrderSide.BUY:
                        p.pnl = (q.bid - p.open_price) * p.volume * self.instruments[p.symbol].contract_size
                    else:
                        p.pnl = (p.open_price - q.ask) * p.volume * self.instruments[p.symbol].contract_size
                    unrealized_pnl += p.pnl
        self.equity = self.balance + unrealized_pnl

    def submit_order(self, order: ApprovedOrder) -> ExecutionResult:
        if order.intent.symbol not in self.quotes:
            return ExecutionResult(success=False, error_message="No quote for symbol")
            
        q = self.quotes[order.intent.symbol]
        price = q.ask if order.intent.side == OrderSide.BUY else q.bid
        
        fill = Fill(
            order_id=str(uuid4()),
            symbol=order.intent.symbol,
            volume=order.intent.volume,
            price=price,
            timestamp=self.current_time,
            commission=0.0,
            swap=0.0
        )
        
        pos = Position(
            id=uuid4(),
            symbol=order.intent.symbol,
            side=order.intent.side,
            volume=order.intent.volume,
            open_price=price,
            open_timestamp=self.current_time,
            state=PositionState.OPEN,
            sl=order.intent.sl,
            tp=order.intent.tp
        )
        self.positions.append(pos)
        self._update_equity()
        
        return ExecutionResult(success=True, order_id=fill.order_id, fill=fill)

    def close_position(self, pos_id: str) -> bool:
        for p in self.positions:
            if str(p.id) == pos_id and p.state == PositionState.OPEN:
                q = self.quotes.get(p.symbol)
                if not q:
                    return False
                close_price = q.bid if p.side == OrderSide.BUY else q.ask
                p.close_price = close_price
                p.close_timestamp = self.current_time
                p.state = PositionState.CLOSED
                
                # Realize PnL
                if p.side == OrderSide.BUY:
                    pnl = (close_price - p.open_price) * p.volume * self.instruments[p.symbol].contract_size
                else:
                    pnl = (p.open_price - close_price) * p.volume * self.instruments[p.symbol].contract_size
                p.pnl = pnl
                self.balance += pnl
                self._update_equity()
                return True
        return False

    def get_account_snapshot(self) -> AccountSnapshot:
        return AccountSnapshot(
            timestamp=self.current_time or datetime.utcnow(),
            balance=self.balance,
            equity=self.equity,
            margin=self.margin,
            margin_free=self.equity - self.margin,
            margin_level=100.0 if self.margin == 0 else (self.equity / self.margin) * 100,
            currency=self.currency
        )
