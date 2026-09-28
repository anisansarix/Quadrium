from datetime import UTC, datetime
from uuid import uuid4

from app.domain.models import (
    AccountSnapshot,
    ApprovedOrder,
    ExecutionResult,
    Fill,
    InstrumentSpec,
    OrderSide,
    Position,
    PositionState,
    Quote,
)


class SimulatorEngine:
    def __init__(self, initial_balance: float = 10000.0, currency: str = "USD"):
        self.balance = initial_balance
        self.equity = initial_balance
        self.margin = 0.0
        self.currency = currency
        self.positions: list[Position] = []
        self.current_time: datetime | None = None
        self.quotes: dict[str, Quote] = {}
        self.instruments: dict[str, InstrumentSpec] = {}
        
    def set_instrument(self, spec: InstrumentSpec):
        self.instruments[spec.canonical_symbol] = spec

    def update_quote(self, quote: Quote):
        self.quotes[quote.symbol] = quote
        self.current_time = quote.timestamp
        self._update_equity()
        self._check_sl_tp()

    def _update_equity(self):
        unrealized_pnl = 0.0
        for p in self.positions:
            if p.state == PositionState.OPEN:
                q = self.quotes.get(p.symbol)
                if q:
                    if p.side == OrderSide.BUY:
                        p.pnl = (q.bid - p.open_price) * p.volume * self.instruments[p.symbol].contract_size
                    else:
                        p.pnl = (p.open_price - q.ask) * p.volume * self.instruments[p.symbol].contract_size
                    unrealized_pnl += p.pnl - p.commission - p.swap
        self.equity = self.balance + unrealized_pnl

    def _check_sl_tp(self):
        for p in self.positions:
            if p.state == PositionState.OPEN:
                q = self.quotes.get(p.symbol)
                if q:
                    if p.side == OrderSide.BUY:
                        if p.sl and q.bid <= p.sl or p.tp and q.bid >= p.tp:
                            self.close_position(str(p.id), q.bid)
                    else:
                        if p.sl and q.ask >= p.sl or p.tp and q.ask <= p.tp:
                            self.close_position(str(p.id), q.ask)

    def submit_order(self, order: ApprovedOrder) -> ExecutionResult:
        if order.intent.symbol not in self.quotes:
            return ExecutionResult(success=False, error_message="No quote for symbol")
            
        q = self.quotes[order.intent.symbol]
        price = q.ask if order.intent.side == OrderSide.BUY else q.bid
        
        # Netting logic (simplified FIFO)
        remaining_vol = order.intent.volume
        
        for p in self.positions:
            if p.state == PositionState.OPEN and p.symbol == order.intent.symbol and p.side != order.intent.side:
                if p.volume <= remaining_vol:
                    self.close_position(str(p.id), price)
                    remaining_vol -= p.volume
                else:
                    self.reduce_position(str(p.id), remaining_vol, price)
                    remaining_vol = 0
                    break
                    
        if remaining_vol > 0:
            fill = Fill(
                order_id=str(uuid4()),
                symbol=order.intent.symbol,
                volume=remaining_vol,
                price=price,
                timestamp=self.current_time, # type: ignore
                commission=0.0,
                swap=0.0
            )
            
            pos = Position(
                id=uuid4(),
                symbol=order.intent.symbol,
                side=order.intent.side,
                volume=remaining_vol,
                open_price=price,
                open_timestamp=self.current_time, # type: ignore
                state=PositionState.OPEN,
                sl=order.intent.sl,
                tp=order.intent.tp
            )
            self.positions.append(pos)
            self._update_equity()
            return ExecutionResult(success=True, order_id=fill.order_id, fill=fill)
            
        return ExecutionResult(success=True, order_id="netted")

    def reduce_position(self, pos_id: str, amount: float, close_price: float) -> bool:
        for p in self.positions:
            if str(p.id) == pos_id and p.state == PositionState.OPEN:
                p.volume -= amount
                # realize partial pnl
                if p.side == OrderSide.BUY:
                    pnl = (close_price - p.open_price) * amount * self.instruments[p.symbol].contract_size
                else:
                    pnl = (p.open_price - close_price) * amount * self.instruments[p.symbol].contract_size
                self.balance += pnl
                self._update_equity()
                return True
        return False

    def close_position(self, pos_id: str, close_price: float | None = None) -> bool:
        for p in self.positions:
            if str(p.id) == pos_id and p.state == PositionState.OPEN:
                q = self.quotes.get(p.symbol)
                if not q: return False
                
                cp = close_price if close_price else (q.bid if p.side == OrderSide.BUY else q.ask)
                p.close_price = cp
                p.close_timestamp = self.current_time
                p.state = PositionState.CLOSED
                
                if p.side == OrderSide.BUY:
                    pnl = (cp - p.open_price) * p.volume * self.instruments[p.symbol].contract_size
                else:
                    pnl = (p.open_price - cp) * p.volume * self.instruments[p.symbol].contract_size
                p.pnl = pnl
                self.balance += pnl - p.commission - p.swap
                self._update_equity()
                return True
        return False

    def get_account_snapshot(self) -> AccountSnapshot:
        return AccountSnapshot(
            timestamp=self.current_time or datetime.now(UTC),
            balance=self.balance,
            equity=self.equity,
            margin=self.margin,
            margin_free=self.equity - self.margin,
            margin_level=100.0 if self.margin == 0 else (self.equity / self.margin) * 100,
            currency=self.currency
        )
