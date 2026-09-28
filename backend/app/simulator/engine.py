from datetime import UTC, datetime
from uuid import uuid4

from app.domain.models import (
    AccountSnapshot,
    AccountState,
    ApprovedOrder,
    ClosedTrade,
    ExecutionResult,
    ExecutionRole,
    Fill,
    InstrumentSpec,
    OrderSide,
    Position,
    PositionState,
    Quote,
    SimulationEvent,
)
from app.simulator.models.commission import CommissionModel, ZeroCommissionModel
from app.simulator.models.currency import CurrencyConversionModel, DeterministicUSDModel
from app.simulator.models.fill_policy import IntrabarFillPolicy, SLTriggerQuote
from app.simulator.models.margin import DeterministicMarginModel, MarginModel
from app.simulator.models.slippage import SlippageModel, ZeroSlippageModel
from app.simulator.models.swap import SwapModel, ZeroSwapModel


class SimulatorEngine:
    def __init__(
        self,
        initial_balance: float = 10000.0,
        currency: str = "USD",
        leverage: float = 30.0,
        commission_model: CommissionModel | None = None,
        swap_model: SwapModel | None = None,
        slippage_model: SlippageModel | None = None,
        margin_model: MarginModel | None = None,
        currency_model: CurrencyConversionModel | None = None,
        fill_policy: IntrabarFillPolicy | None = None
    ):
        self.balance = initial_balance
        self.equity = initial_balance
        self.margin = 0.0
        self.currency = currency
        self.leverage = leverage
        self.positions: list[Position] = []
        self.current_time: datetime | None = None
        self.quotes: dict[str, Quote] = {}
        self.instruments: dict[str, InstrumentSpec] = {}
        
        self.commission_model = commission_model or ZeroCommissionModel()
        self.swap_model = swap_model or ZeroSwapModel()
        self.slippage_model = slippage_model or ZeroSlippageModel()
        self.margin_model = margin_model or DeterministicMarginModel()
        self.currency_model = currency_model or DeterministicUSDModel()
        self.fill_policy = fill_policy or IntrabarFillPolicy()
        
        self.account_state = AccountState.NORMAL

    def set_instrument(self, spec: InstrumentSpec) -> None:
        self.instruments[spec.canonical_symbol] = spec

    def update_quote(self, quote: Quote) -> SimulationEvent:
        self.quotes[quote.symbol] = quote
        self.current_time = quote.timestamp
        self._update_equity()
        
        # Check SL/TP
        fills = []
        closed_trades = []
        for p in self.positions:
            if p.state == PositionState.OPEN:
                q = self.quotes.get(p.symbol)
                if not q:
                    continue
                
                if p.sl is not None:
                    trigger_price = self._get_trigger_price(q, self.fill_policy.long_sl_trigger if p.side == OrderSide.BUY else self.fill_policy.short_sl_trigger)
                    if (p.side == OrderSide.BUY and trigger_price <= p.sl) or (p.side == OrderSide.SELL and trigger_price >= p.sl):
                        ct, f = self.close_position(str(p.id), trigger_price, "SL")
                        if ct and f:
                            closed_trades.append(ct)
                            fills.append(f)
                        continue
                
                if p.tp is not None:
                    trigger_price = self._get_trigger_price(q, self.fill_policy.long_tp_trigger if p.side == OrderSide.BUY else self.fill_policy.short_tp_trigger)
                    if (p.side == OrderSide.BUY and trigger_price >= p.tp) or (p.side == OrderSide.SELL and trigger_price <= p.tp):
                        ct, f = self.close_position(str(p.id), trigger_price, "TP")
                        if ct and f:
                            closed_trades.append(ct)
                            fills.append(f)
                            
        return SimulationEvent(
            timestamp=self.current_time or datetime.now(UTC),
            fills=fills,
            closed_trades=closed_trades,
            risk_events=[]
        )

    def _update_equity(self) -> None:
        unrealized_pnl = 0.0
        used_margin = 0.0
        for p in self.positions:
            if p.state == PositionState.OPEN:
                q = self.quotes.get(p.symbol)
                if q:
                    if p.side == OrderSide.BUY:
                        p.pnl = (q.bid - p.open_price) * p.volume * self.instruments[p.symbol].contract_size
                    else:
                        p.pnl = (p.open_price - q.ask) * p.volume * self.instruments[p.symbol].contract_size
                    unrealized_pnl += p.pnl
                    
                    m = self.margin_model.calculate_margin(p.symbol, p.volume, p.open_price, self.instruments[p.symbol].contract_size, self.leverage)
                    used_margin += m
                    
        self.equity = self.balance + unrealized_pnl
        self.margin = used_margin

    def _get_trigger_price(self, quote: Quote, trigger: SLTriggerQuote) -> float:
        return quote.bid if trigger == SLTriggerQuote.BID else quote.ask
        
    def freeze_account(self) -> None:
        if self.account_state != AccountState.FLATTEN_AND_FREEZE:
            self.account_state = AccountState.FREEZE
            
    def flatten_positions(self, reason: str = "FLATTEN") -> tuple[list[ClosedTrade], list[Fill]]:
        closed_trades = []
        fills = []
        for p in self.positions:
            if p.state == PositionState.OPEN:
                ct, f = self.close_position(str(p.id), reason=reason)
                if ct and f:
                    closed_trades.append(ct)
                    fills.append(f)
        return closed_trades, fills
        
    def flatten_and_freeze(self, reason: str = "FLATTEN_AND_FREEZE") -> tuple[list[ClosedTrade], list[Fill]]:
        self.account_state = AccountState.FLATTEN_AND_FREEZE
        return self.flatten_positions(reason)

    def submit_order(self, order: ApprovedOrder) -> ExecutionResult:
        if self.account_state in [AccountState.FREEZE, AccountState.FLATTEN_AND_FREEZE]:
            return ExecutionResult(success=False, error_message="Account is frozen")

        if order.intent.symbol not in self.quotes:
            return ExecutionResult(success=False, error_message="No quote for symbol")
            
        q = self.quotes[order.intent.symbol]
        requested_price = q.ask if order.intent.side == OrderSide.BUY else q.bid
        fill_price = self.slippage_model.apply_slippage(order.intent.symbol, requested_price, order.intent.side == OrderSide.BUY)
        
        remaining_vol = order.intent.volume
        fills = []
        closed_trades = []
        
        for p in self.positions:
            if p.state == PositionState.OPEN and p.symbol == order.intent.symbol and p.side != order.intent.side:
                if p.volume <= remaining_vol:
                    ct, f = self.close_position(str(p.id), fill_price, "REVERSAL_NETTING")
                    if ct and f:
                        closed_trades.append(ct)
                        fills.append(f)
                    remaining_vol -= p.volume
                else:
                    ct, f = self.reduce_position(str(p.id), remaining_vol, fill_price, "PARTIAL_CLOSE")
                    if ct and f:
                        closed_trades.append(ct)
                        fills.append(f)
                    remaining_vol = 0
                    break
                    
        if remaining_vol > 0:
            entry_comm = self.commission_model.calculate_commission(order.intent.symbol, remaining_vol)
            self.balance -= entry_comm # Realized entry cost
            
            pos_id = uuid4()
            exec_role = ExecutionRole.REVERSAL if closed_trades else (
                ExecutionRole.INCREASE if any(p.side == order.intent.side and p.symbol == order.intent.symbol for p in self.positions if p.state == PositionState.OPEN) else ExecutionRole.ENTRY
            )
            
            fill = Fill(
                order_id=str(uuid4()),
                position_id=pos_id,
                symbol=order.intent.symbol,
                side=order.intent.side,
                execution_role=exec_role,
                volume=remaining_vol,
                price=fill_price,
                timestamp=self.current_time or datetime.now(UTC),
                commission=entry_comm,
                swap=0.0,
                realized_pnl=0.0
            )
            
            pos = Position(
                id=pos_id,
                symbol=order.intent.symbol,
                side=order.intent.side,
                volume=remaining_vol,
                open_price=fill_price,
                open_timestamp=self.current_time or datetime.now(UTC),
                state=PositionState.OPEN,
                sl=order.intent.sl,
                tp=order.intent.tp,
                commission=entry_comm
            )
            self.positions.append(pos)
            fills.append(fill)
            self._update_equity()
            
        return ExecutionResult(
            success=True,
            order_id=fills[0].order_id if fills else "netted",
            fills=fills,
            closed_trades=closed_trades
        )

    def reduce_position(self, pos_id: str, amount: float, close_price: float, reason: str = "PARTIAL_CLOSE") -> tuple[ClosedTrade | None, Fill | None]:
        for p in self.positions:
            if str(p.id) == pos_id and p.state == PositionState.OPEN:
                if p.side == OrderSide.BUY:
                    realized_pnl = (close_price - p.open_price) * amount * self.instruments[p.symbol].contract_size
                else:
                    realized_pnl = (p.open_price - close_price) * amount * self.instruments[p.symbol].contract_size
                
                prorata_ratio = amount / p.volume
                realized_entry_comm = p.commission * prorata_ratio
                realized_swap = p.swap * prorata_ratio
                
                # Charge exit commission
                exit_comm = self.commission_model.calculate_commission(p.symbol, amount)
                self.balance -= exit_comm
                
                p.volume -= amount
                p.commission -= realized_entry_comm
                p.swap -= realized_swap
                
                self.balance += realized_pnl
                self._update_equity()
                
                close_time = self.current_time or datetime.now(UTC)
                holding_secs = (close_time - p.open_timestamp).total_seconds()
                
                ct = ClosedTrade(
                    trade_id=str(uuid4()),
                    symbol=p.symbol,
                    side=p.side.value,
                    entry_time=p.open_timestamp,
                    exit_time=close_time,
                    entry_price=p.open_price,
                    exit_price=close_price,
                    entry_volume=amount,
                    exit_volume=amount,
                    gross_pnl=realized_pnl,
                    entry_commission=realized_entry_comm,
                    exit_commission=exit_comm,
                    swap=realized_swap,
                    net_pnl=realized_pnl - realized_entry_comm - exit_comm - realized_swap,
                    holding_seconds=holding_secs,
                    exit_reason=reason
                )
                f = Fill(
                    order_id=ct.trade_id,
                    position_id=p.id,
                    symbol=p.symbol,
                    side=OrderSide.SELL if p.side == OrderSide.BUY else OrderSide.BUY,
                    execution_role=ExecutionRole.REDUCE,
                    volume=amount,
                    price=close_price,
                    timestamp=close_time,
                    commission=exit_comm,
                    swap=0.0,
                    realized_pnl=realized_pnl
                )
                return ct, f
        return None, None

    def close_position(self, pos_id: str, close_price: float | None = None, reason: str = "CLOSE") -> tuple[ClosedTrade | None, Fill | None]:
        for p in self.positions:
            if str(p.id) == pos_id and p.state == PositionState.OPEN:
                q = self.quotes.get(p.symbol)
                if not q: return None, None
                
                cp = close_price if close_price else (q.bid if p.side == OrderSide.BUY else q.ask)
                p.close_price = cp
                p.close_timestamp = self.current_time or datetime.now(UTC)
                p.state = PositionState.CLOSED
                
                if p.side == OrderSide.BUY:
                    realized_pnl = (cp - p.open_price) * p.volume * self.instruments[p.symbol].contract_size
                else:
                    realized_pnl = (p.open_price - cp) * p.volume * self.instruments[p.symbol].contract_size
                p.pnl = realized_pnl
                
                # Charge exit commission
                exit_comm = self.commission_model.calculate_commission(p.symbol, p.volume)
                self.balance -= exit_comm
                
                self.balance += realized_pnl
                self._update_equity()
                
                holding_secs = (p.close_timestamp - p.open_timestamp).total_seconds()
                
                ct = ClosedTrade(
                    trade_id=str(p.id),
                    symbol=p.symbol,
                    side=p.side.value,
                    entry_time=p.open_timestamp,
                    exit_time=p.close_timestamp,
                    entry_price=p.open_price,
                    exit_price=cp,
                    entry_volume=p.volume,
                    exit_volume=p.volume,
                    gross_pnl=realized_pnl,
                    entry_commission=p.commission,
                    exit_commission=exit_comm,
                    swap=p.swap,
                    net_pnl=realized_pnl - p.commission - exit_comm - p.swap,
                    holding_seconds=holding_secs,
                    exit_reason=reason
                )
                role_map = {
                    "SL": ExecutionRole.SL,
                    "TP": ExecutionRole.TP,
                    "FLATTEN": ExecutionRole.FLATTEN,
                    "FLATTEN_AND_FREEZE": ExecutionRole.FLATTEN
                }
                exec_role = role_map.get(reason, ExecutionRole.CLOSE)
                
                f = Fill(
                    order_id=str(p.id),
                    position_id=p.id,
                    symbol=p.symbol,
                    side=OrderSide.SELL if p.side == OrderSide.BUY else OrderSide.BUY,
                    execution_role=exec_role,
                    volume=p.volume,
                    price=cp,
                    timestamp=p.close_timestamp,
                    commission=exit_comm,
                    swap=0.0,
                    realized_pnl=realized_pnl
                )
                return ct, f
        return None, None

    def get_account_snapshot(self) -> AccountSnapshot:
        return AccountSnapshot(
            timestamp=self.current_time or datetime.now(UTC),
            balance=self.balance,
            equity=self.equity,
            margin=self.margin,
            margin_free=self.equity - self.margin,
            margin_level=100.0 if self.margin == 0 else (self.equity / self.margin) * 100,
            currency=self.currency,
            state=self.account_state
        )
