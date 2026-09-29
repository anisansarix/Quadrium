import uuid
from datetime import UTC, datetime

import pandas as pd

from app.domain.models import (
    AccountState,
    ExecutionRole,
    FeatureState,
    Fill,
    OrderSide,
    Position,
    PositionState,
)
from app.simulator.domain import (
    ActionProposal,
    MarketObservation,
    PortfolioState,
    SimulatorStepResult,
)


class TransactionCostModel:
    def __init__(self, commission_per_unit: float = 0.0, slippage_points: float = 0.0, point_value: float = 0.00001, contract_size: float = 100000.0):
        self.commission_per_unit = commission_per_unit
        self.slippage_points = slippage_points
        self.point_value = point_value
        self.contract_size = contract_size

class PolicySimulator:
    def __init__(self, initial_balance: float, cost_model: TransactionCostModel, max_position_units: float = 1.0):
        self.balance = initial_balance
        self.cost_model = cost_model
        self.max_position_units = max_position_units
        
        self.position: Position | None = None
        self.current_time: datetime | None = None
        self.account_state = AccountState.NORMAL
        self.symbol = "EURUSD" # Fixed for now as single-asset env

    def get_portfolio_state(self, mark_price: float) -> PortfolioState:
        unrealized = 0.0
        pos_dict = {}
        if self.position and self.position.state == PositionState.OPEN:
            if self.position.side == OrderSide.BUY:
                unrealized = (mark_price - self.position.open_price) * self.position.volume * self.cost_model.contract_size
            else:
                unrealized = (self.position.open_price - mark_price) * self.position.volume * self.cost_model.contract_size
            pos_dict[self.symbol] = self.position

        return PortfolioState(
            timestamp=self.current_time or datetime.now(UTC),
            balance=self.balance,
            equity=self.balance + unrealized,
            unrealized_pnl=unrealized,
            positions=pos_dict,
            state=self.account_state
        )

    def _execute_trade(self, trade_vol: float, side: OrderSide, exec_price: float, spread: float, timestamp: datetime, role: ExecutionRole) -> tuple[Fill, float]:
        comm = self.cost_model.commission_per_unit * trade_vol
        self.balance -= comm
        
        slip_amt = self.cost_model.slippage_points * self.cost_model.point_value
        
        # If BUY, pay ASK (price + spread). If SELL, receive BID (price).
        # Assuming exec_price is the BID price (standard OHLC usually represents BID).
        actual_price = exec_price + spread + slip_amt if side == OrderSide.BUY else exec_price - slip_amt
        
        fill = Fill(
            order_id=str(uuid.uuid4()),
            position_id=None, 
            symbol=self.symbol,
            side=side,
            execution_role=role,
            volume=trade_vol,
            price=actual_price,
            timestamp=timestamp,
            commission=comm,
            swap=0.0
        )
        return fill, actual_price

    def _flatten_position(self, exec_price: float, spread: float, timestamp: datetime) -> tuple[Fill, float]:
        if not self.position or self.position.state == PositionState.CLOSED:
            raise ValueError("No open position to flatten")
            
        close_side = OrderSide.SELL if self.position.side == OrderSide.BUY else OrderSide.BUY
        fill, actual_price = self._execute_trade(self.position.volume, close_side, exec_price, spread, timestamp, ExecutionRole.FLATTEN)
        
        if self.position.side == OrderSide.BUY:
            realized_pnl = (actual_price - self.position.open_price) * self.position.volume * self.cost_model.contract_size
        else:
            realized_pnl = (self.position.open_price - actual_price) * self.position.volume * self.cost_model.contract_size
            
        self.balance += realized_pnl
        self.position.state = PositionState.CLOSED
        self.position.close_price = actual_price
        self.position = None
        
        return fill, realized_pnl

    def _open_position(self, vol: float, side: OrderSide, exec_price: float, spread: float, timestamp: datetime) -> Fill:
        fill, actual_price = self._execute_trade(vol, side, exec_price, spread, timestamp, ExecutionRole.ENTRY)
        
        pos_id = uuid.uuid4()
        fill.position_id = pos_id
        
        self.position = Position(
            id=pos_id,
            symbol=self.symbol,
            side=side,
            volume=vol,
            open_price=actual_price,
            open_timestamp=timestamp,
            state=PositionState.OPEN,
            commission=fill.commission
        )
        return fill

    def process_step(self, action: ActionProposal, next_row: pd.Series) -> SimulatorStepResult:
        # Timing semantics:
        # We are at decision time t+delta. We evaluated features from the PREVIOUS bar.
        # The exact execution price is the OPEN price of next_row (which represents the bar starting at t+delta).
        # We process the action, then return the observation at the END of next_row.
        
        exec_price = next_row['open']
        spread = next_row['spread'] * self.cost_model.point_value
        timestamp = next_row['timestamp'] # The precise time of execution (t+delta)
        
        # Check invalid data behavior BEFORE executing action
        if next_row['feature_state'] == FeatureState.INVALID or next_row['feature_state'] == FeatureState.WARMUP:
            # Flatten to prevent blind risk
            fills = []
            realized_pnl = 0.0
            if self.position and self.position.state == PositionState.OPEN:
                f, p = self._flatten_position(exec_price, spread, timestamp)
                fills.append(f)
                realized_pnl += p
            
            self.current_time = timestamp
            return SimulatorStepResult(
                timestamp=timestamp,
                observation=None, # Invalid observation
                portfolio=self.get_portfolio_state(next_row['close']),
                fills=fills,
                realized_pnl=realized_pnl,
            step_reward=0.0,
                is_done=True, # Breaking contiguity stops the episode
                info={"reason": "INVALID_DATA_FORCED_FLATTEN"}
            )
            
        target_vol = abs(action.target_weight) * self.max_position_units
        target_side = OrderSide.BUY if action.target_weight > 0 else (OrderSide.SELL if action.target_weight < 0 else None)
        
        fills = []
        realized_pnl = 0.0
        
        if self.position and self.position.state == PositionState.OPEN:
            if target_side is None:
                # Flat
                f, p = self._flatten_position(exec_price, spread, timestamp)
                fills.append(f)
                realized_pnl += p
            elif target_side != self.position.side:
                # Reversal
                f, p = self._flatten_position(exec_price, spread, timestamp)
                fills.append(f)
                realized_pnl += p
                f2 = self._open_position(target_vol, target_side, exec_price, spread, timestamp)
                fills.append(f2)
            else:
                # Same side, volume change
                vol_diff = target_vol - self.position.volume
                if vol_diff > 1e-7: # Increase
                    f, _ = self._execute_trade(vol_diff, target_side, exec_price, spread, timestamp, ExecutionRole.INCREASE)
                    # Average entry price
                    old_value = self.position.volume * self.position.open_price
                    new_value = vol_diff * f.price
                    self.position.volume += vol_diff
                    self.position.open_price = (old_value + new_value) / self.position.volume
                    self.position.commission += f.commission
                    fills.append(f)
                elif vol_diff < -1e-7: # Reduce
                    reduce_vol = abs(vol_diff)
                    close_side = OrderSide.SELL if self.position.side == OrderSide.BUY else OrderSide.BUY
                    f, actual_price = self._execute_trade(reduce_vol, close_side, exec_price, spread, timestamp, ExecutionRole.REDUCE)
                    
                    if self.position.side == OrderSide.BUY:
                        rp = (actual_price - self.position.open_price) * reduce_vol * self.cost_model.contract_size
                    else:
                        rp = (self.position.open_price - actual_price) * reduce_vol * self.cost_model.contract_size
                        
                    self.balance += rp
                    realized_pnl += rp
                    self.position.volume -= reduce_vol
                    fills.append(f)
        else:
            if target_side is not None and target_vol > 1e-7:
                f = self._open_position(target_vol, target_side, exec_price, spread, timestamp)
                fills.append(f)
                
        self.current_time = timestamp
        
        obs = MarketObservation(
            timestamp=next_row['timestamp'], # Time of next action decision
            symbol=self.symbol,
            features={c: next_row[c] for c in ['ret_1', 'spread_level'] if c in next_row},
            close_price=next_row['close']
        )
        
        return SimulatorStepResult(
            timestamp=timestamp,
            observation=obs,
            portfolio=self.get_portfolio_state(next_row['close']),
            fills=fills,
            realized_pnl=realized_pnl,
            step_reward=0.0,
            is_done=False,
            info={}
        )


