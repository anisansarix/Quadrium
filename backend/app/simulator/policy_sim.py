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
        if commission_per_unit < 0 or slippage_points < 0 or point_value < 0 or contract_size < 0:
            raise ValueError("Cost model parameters cannot be negative")
        self.commission_per_unit = commission_per_unit
        self.slippage_points = slippage_points
        self.point_value = point_value
        self.contract_size = contract_size

class PolicySimulator:
    def __init__(self, initial_balance: float, cost_model: TransactionCostModel, symbol: str, max_position_units: float = 1.0):
        if max_position_units < 0:
            raise ValueError("Max position units cannot be negative")
        self.balance = initial_balance
        self.cost_model = cost_model
        self.symbol = symbol
        self.max_position_units = max_position_units

        self.position: Position | None = None
        self.current_time: datetime | None = None
        self.last_valid_close: float | None = None
        self.account_state = AccountState.NORMAL

        self.step_counter = 0
        self.fill_counter = 0
        self.position_counter = 0

    def get_portfolio_state(self, mark_price_bid: float, spread: float) -> PortfolioState:
        if self.current_time is None:
            raise ValueError("Cannot get portfolio state before simulator has started")

        unrealized = 0.0
        pos_dict = {}
        if self.position and self.position.state == PositionState.OPEN:
            if self.position.side == OrderSide.BUY:
                unrealized = (mark_price_bid - self.position.open_price) * self.position.volume * self.cost_model.contract_size
            else:
                ask_price = mark_price_bid + spread
                unrealized = (self.position.open_price - ask_price) * self.position.volume * self.cost_model.contract_size
            pos_dict[self.symbol] = self.position

        return PortfolioState(
            timestamp=self.current_time,
            balance=self.balance,
            equity=self.balance + unrealized,
            unrealized_pnl=unrealized,
            positions=pos_dict,
            state=self.account_state
        )

    def _generate_fill_id(self) -> str:
        self.fill_counter += 1
        return f"fill_{self.step_counter}_{self.fill_counter}"

    def _generate_pos_id(self) -> str:
        self.position_counter += 1
        return f"pos_{self.step_counter}_{self.position_counter}"

    def _execute_trade(self, trade_vol: float, side: OrderSide, exec_price_bid: float, spread: float, timestamp: datetime, role: ExecutionRole) -> tuple[Fill, float]:
        comm = self.cost_model.commission_per_unit * trade_vol
        self.balance -= comm

        slip_amt = self.cost_model.slippage_points * self.cost_model.point_value

        if side == OrderSide.BUY:
            actual_price = exec_price_bid + spread + slip_amt
        else:
            actual_price = exec_price_bid - slip_amt

        fill = Fill(
            order_id=self._generate_fill_id(),
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

    def _flatten_position(self, exec_price_bid: float, spread: float, timestamp: datetime) -> tuple[Fill, float]:
        if not self.position or self.position.state == PositionState.CLOSED:
            raise ValueError("No open position to flatten")

        close_side = OrderSide.SELL if self.position.side == OrderSide.BUY else OrderSide.BUY
        fill, actual_price = self._execute_trade(self.position.volume, close_side, exec_price_bid, spread, timestamp, ExecutionRole.FLATTEN)

        if self.position.side == OrderSide.BUY:
            realized_pnl = (actual_price - self.position.open_price) * self.position.volume * self.cost_model.contract_size
        else:
            realized_pnl = (self.position.open_price - actual_price) * self.position.volume * self.cost_model.contract_size

        self.balance += realized_pnl
        self.position.state = PositionState.CLOSED
        self.position.close_price = actual_price
        fill.position_id = self.position.id
        self.position = None

        return fill, realized_pnl

    def _open_position(self, vol: float, side: OrderSide, exec_price_bid: float, spread: float, timestamp: datetime) -> Fill:
        fill, actual_price = self._execute_trade(vol, side, exec_price_bid, spread, timestamp, ExecutionRole.ENTRY)

        pos_id = uuid.uuid5(uuid.NAMESPACE_OID, self._generate_pos_id())
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

    def process_step(self, action: ActionProposal | None, next_row: pd.Series | None) -> SimulatorStepResult:
        self.step_counter += 1

        if action and action.symbol != self.symbol:
            raise ValueError(f"Action symbol {action.symbol} does not match simulator symbol {self.symbol}")

        if next_row is None:
            fills = []
            realized_pnl = 0.0
            if self.position and self.position.state == PositionState.OPEN:
                if self.last_valid_close is None or self.current_time is None:
                    raise ValueError("Cannot flatten on end-of-data with no last valid close/timestamp")
                f, p = self._flatten_position(self.last_valid_close, 0.0, self.current_time)
                fills.append(f)
                realized_pnl += p

            return SimulatorStepResult(
                timestamp=self.current_time or datetime.now(UTC),
                observation=None,
                portfolio=self.get_portfolio_state(self.last_valid_close or 0.0, 0.0),
                fills=fills,
                realized_pnl=realized_pnl,
                is_done=True,
                info={"reason": "END_OF_DATA"}
            )

        timestamp: datetime = next_row['timestamp']
        self.current_time = timestamp

        if pd.isna(next_row['open']):
            exec_price = self.last_valid_close
        else:
            exec_price = float(next_row['open'])

        spread = float(next_row['spread']) * self.cost_model.point_value if not pd.isna(next_row.get('spread')) else 0.0

        if next_row['feature_state'] == FeatureState.INVALID:
            fills = []
            realized_pnl = 0.0
            if self.position and self.position.state == PositionState.OPEN:
                if exec_price is None:
                    raise ValueError("No valid execution price available to flatten invalid state")
                f, p = self._flatten_position(exec_price, spread, timestamp)
                fills.append(f)
                realized_pnl += p

            return SimulatorStepResult(
                timestamp=timestamp,
                observation=None,
                portfolio=self.get_portfolio_state(exec_price or 0.0, spread),
                fills=fills,
                realized_pnl=realized_pnl,
                is_done=True,
                info={"reason": "INVALID_DATA"}
            )

        if next_row['feature_state'] == FeatureState.WARMUP:
            self.last_valid_close = float(next_row['close']) if not pd.isna(next_row.get('close')) else self.last_valid_close
            return SimulatorStepResult(
                timestamp=timestamp,
                observation=None,
                portfolio=self.get_portfolio_state(self.last_valid_close or 0.0, spread),
                fills=[],
                realized_pnl=0.0,
                is_done=False,
                info={"reason": "WARMUP"}
            )

        fills = []
        realized_pnl = 0.0

        if exec_price is None:
            raise ValueError("No execution price available")

        if action is not None:
            target_vol = abs(action.target_weight) * self.max_position_units
            target_side = OrderSide.BUY if action.target_weight > 0 else (OrderSide.SELL if action.target_weight < 0 else None)

            if self.position and self.position.state == PositionState.OPEN:
                if target_side is None:
                    f, p = self._flatten_position(exec_price, spread, timestamp)
                    fills.append(f)
                    realized_pnl += p
                elif target_side != self.position.side:
                    f, p = self._flatten_position(exec_price, spread, timestamp)
                    fills.append(f)
                    realized_pnl += p
                    f2 = self._open_position(target_vol, target_side, exec_price, spread, timestamp)
                    fills.append(f2)
                else:
                    vol_diff = target_vol - self.position.volume
                    if vol_diff > 1e-7:
                        f, actual_price = self._execute_trade(vol_diff, target_side, exec_price, spread, timestamp, ExecutionRole.INCREASE)
                        old_value = self.position.volume * self.position.open_price
                        new_value = vol_diff * actual_price
                        self.position.volume += vol_diff
                        self.position.open_price = (old_value + new_value) / self.position.volume
                        self.position.commission += f.commission
                        f.position_id = self.position.id
                        fills.append(f)
                    elif vol_diff < -1e-7:
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
                        f.position_id = self.position.id
                        fills.append(f)
            else:
                if target_side is not None and target_vol > 1e-7:
                    f = self._open_position(target_vol, target_side, exec_price, spread, timestamp)
                    fills.append(f)

        self.last_valid_close = float(next_row['close'])
        obs = MarketObservation(
            timestamp=timestamp,
            symbol=self.symbol,
            features={c: float(next_row[c]) for c in ['ret_1', 'spread_level'] if c in next_row and not pd.isna(next_row[c])},
            close_price=self.last_valid_close
        )

        return SimulatorStepResult(
            timestamp=timestamp,
            observation=obs,
            portfolio=self.get_portfolio_state(self.last_valid_close, spread),
            fills=fills,
            realized_pnl=realized_pnl,
            is_done=False,
            info={}
        )
