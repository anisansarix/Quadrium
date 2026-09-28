from datetime import datetime
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
from app.simulator.models.commission import CommissionModel, ZeroCommissionModel
from app.simulator.models.swap import SwapModel, ZeroSwapModel
from app.simulator.models.slippage import SlippageModel, ZeroSlippageModel
from app.simulator.models.margin import MarginModel, DeterministicMarginModel
from app.simulator.models.currency import CurrencyConversionModel, DeterministicUSDModel
from app.simulator.models.fill_policy import IntrabarFillPolicy

class SimulatorEngine:
    def __init__(
        self,
        initial_balance: float = 10000.0,
        currency: str = "USD",
        commission_model: CommissionModel = ZeroCommissionModel(),
        swap_model: SwapModel = ZeroSwapModel(),
        slippage_model: SlippageModel = ZeroSlippageModel(),
        margin_model: MarginModel = DeterministicMarginModel(),
        currency_model: CurrencyConversionModel = DeterministicUSDModel(),
        fill_policy: IntrabarFillPolicy = IntrabarFillPolicy()
    ):
        self.balance = initial_balance
        self.equity = initial_balance
        self.margin = 0.0
        self.currency = currency
        self.positions: list[Position] = []
        self.current_time: datetime | None = None
        self.quotes: dict[str, Quote] = {}
        self.instruments: dict[str, InstrumentSpec] = {}
        
        self.commission_model = commission_model
        self.swap_model = swap_model
        self.slippage_model = slippage_model
        self.margin_model = margin_model
        self.currency_model = currency_model
        self.fill_policy = fill_policy

    def set_instrument(self, spec: InstrumentSpec) -> None:
        self.instruments[spec.canonical_symbol] = spec

    def update_quote(self, quote: Quote) -> None:
        self.quotes[quote.symbol] = quote
        self.current_time = quote.timestamp
        self._update_equity()
        self._check_sl_tp()

    def _update_equity(self) -> None:
        unrealized_pnl = 0.0
        used_margin = 0.0
        for p in self.positions:
            if p.state == PositionState.OPEN:
                q = self.quotes.get(p.symbol)
                if q:
                    # Mark-to-market
                    if p.side == OrderSide.BUY:
                        p.pnl = (q.bid - p.open_price) * p.volume * self.instruments[p.symbol].contract_size
                    else:
                        p.pnl = (p.open_price - q.ask) * p.volume * self.instruments[p.symbol].contract_size
                    unrealized_pnl += p.pnl - p.commission - p.swap
                    
                    # Margin
                    lev = 30.0 # TODO pass real leverage
                    m = self.margin_model.calculate_margin(p.symbol, p.volume, p.open_price, self.instruments[p.symbol].contract_size, lev)
                    used_margin += m
                    
        self.equity = self.balance + unrealized_pnl
        self.margin = used_margin

    def _check_sl_tp(self) -> None:
        for p in self.positions:
            if p.state == PositionState.OPEN:
                q = self.quotes.get(p.symbol)
                if q:
                    if p.side == OrderSide.BUY:
                        if p.sl is not None and q.bid <= p.sl:
                            self.close_position(str(p.id), q.bid)
                        elif p.tp is not None and q.bid >= p.tp:
                            self.close_position(str(p.id), q.bid)
                    else:
                        if p.sl is not None and q.ask >= p.sl:
                            self.close_position(str(p.id), q.ask)
                        elif p.tp is not None and q.ask <= p.tp:
                            self.close_position(str(p.id), q.ask)

    def submit_order(self, order: ApprovedOrder) -> ExecutionResult:
        if order.intent.symbol not in self.quotes:
            return ExecutionResult(success=False, error_message="No quote for symbol")
            
        q = self.quotes[order.intent.symbol]
        requested_price = q.ask if order.intent.side == OrderSide.BUY else q.bid
        fill_price = self.slippage_model.apply_slippage(order.intent.symbol, requested_price, order.intent.side == OrderSide.BUY)
        
        remaining_vol = order.intent.volume
        fills = []
        
        # Netting logic
        for p in self.positions:
            if p.state == PositionState.OPEN and p.symbol == order.intent.symbol and p.side != order.intent.side:
                if p.volume <= remaining_vol:
                    self.close_position(str(p.id), fill_price)
                    remaining_vol -= p.volume
                else:
                    self.reduce_position(str(p.id), remaining_vol, fill_price)
                    remaining_vol = 0
                    break
                    
        if remaining_vol > 0:
            comm = self.commission_model.calculate_commission(order.intent.symbol, remaining_vol)
            self.balance -= comm # Realized cost
            
            fill = Fill(
                order_id=str(uuid4()),
                symbol=order.intent.symbol,
                volume=remaining_vol,
                price=fill_price,
                timestamp=self.current_time, # type: ignore
                commission=comm,
                swap=0.0
            )
            
            pos = Position(
                id=uuid4(),
                symbol=order.intent.symbol,
                side=order.intent.side,
                volume=remaining_vol,
                open_price=fill_price,
                open_timestamp=self.current_time, # type: ignore
                state=PositionState.OPEN,
                sl=order.intent.sl,
                tp=order.intent.tp,
                commission=comm
            )
            self.positions.append(pos)
            fills.append(fill)
            self._update_equity()
            return ExecutionResult(success=True, order_id=fill.order_id, fill=fill)
            
        self._update_equity()
        return ExecutionResult(success=True, order_id="netted")

    def reduce_position(self, pos_id: str, amount: float, close_price: float) -> bool:
        for p in self.positions:
            if str(p.id) == pos_id and p.state == PositionState.OPEN:
                p.volume -= amount
                if p.side == OrderSide.BUY:
                    pnl = (close_price - p.open_price) * amount * self.instruments[p.symbol].contract_size
                else:
                    pnl = (p.open_price - close_price) * amount * self.instruments[p.symbol].contract_size
                    
                comm_reversal = (amount / (p.volume + amount)) * p.commission
                p.commission -= comm_reversal
                
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
                
                self.balance += pnl
                # Note: commission was already deducted from balance when opened. Swap too.
                self._update_equity()
                return True
        return False

    def get_account_snapshot(self) -> AccountSnapshot:
        from datetime import timezone
        return AccountSnapshot(
            timestamp=self.current_time or datetime.now(timezone.utc),
            balance=self.balance,
            equity=self.equity,
            margin=self.margin,
            margin_free=self.equity - self.margin,
            margin_level=100.0 if self.margin == 0 else (self.equity / self.margin) * 100,
            currency=self.currency
        )
