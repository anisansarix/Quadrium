from typing import Any
from uuid import uuid4

import pandas as pd

from app.core.decision_pipeline import DecisionPipeline
from app.domain.models import (
    BacktestResult,
    ExperimentResult,
    ExperimentSpec,
    InstrumentSpec,
    PositionState,
    Quote,
    RiskContext,
    RiskPolicy,
)
from app.evaluation.ledger import EquityRecord, Ledger
from app.evaluation.metrics import MetricsCalculator
from app.simulator.engine import SimulatorEngine
from app.strategies.baseline import Strategy


class BacktestRunner:
    def __init__(self, simulator: SimulatorEngine, pipeline: DecisionPipeline, policy: RiskPolicy, strategy: Strategy, end_of_test_policy: str = "MARK_TO_MARKET"):
        self.simulator = simulator
        self.pipeline = pipeline
        self.policy = policy
        self.strategy = strategy
        self.ledger = Ledger()
        self.metrics_calculator = MetricsCalculator()
        self.end_of_test_policy = end_of_test_policy
        self.risk_events: list[Any] = []
        
        self.start_of_day_equity = simulator.equity
        self.equity_peak = simulator.equity
        self.initial_balance = simulator.balance

    def run(self, data: list[Quote], spec: InstrumentSpec) -> BacktestResult:
        self.simulator.set_instrument(spec)
        history_records: list[dict[str, Any]] = []
        last_date = None
        
        for q in data:
            self.simulator.update_quote(q)
            history_records.append({
                "timestamp": q.timestamp,
                "close": q.bid,
                "symbol": q.symbol
            })
            
            self.equity_peak = max(self.equity_peak, self.simulator.equity)
            
            current_date = q.timestamp.date()
            if last_date is not None and current_date != last_date:
                self.start_of_day_equity = self.simulator.equity
            last_date = current_date
            
            context = RiskContext(
                account=self.simulator.get_account_snapshot(),
                open_positions=self.simulator.positions,
                current_quote=q,
                instrument=spec,
                start_of_day_equity=self.start_of_day_equity,
                equity_peak=self.equity_peak,
                current_time=q.timestamp
            )
            
            history_df = pd.DataFrame(history_records)
            target = self.strategy.next(q, history_df)
            
            if target:
                approved = self.pipeline.process(target, context, self.policy)
                if approved:
                    self.risk_events.append(approved.risk_decision)
                    res = self.simulator.submit_order(approved)
                    if res.success:
                        for fill in res.fills:
                            from app.evaluation.ledger import ExecutionRecord
                            self.ledger.append_execution(ExecutionRecord(
                                order_id=fill.order_id,
                                symbol=fill.symbol,
                                side=approved.intent.side.value,
                                volume=fill.volume,
                                requested_price=q.ask if approved.intent.side.value == "BUY" else q.bid,
                                fill_price=fill.price,
                                timestamp=fill.timestamp,
                                realized_pnl=fill.realized_pnl,
                                commission=fill.commission,
                                swap=fill.swap
                            ))
                        for ct in res.closed_trades:
                            self.ledger.append_closed_trade(ct)
                            
            # Record Equity at the end of every event
            dd = (self.equity_peak - self.simulator.equity) / self.equity_peak if self.equity_peak > 0 else 0.0
            er = EquityRecord(
                timestamp=q.timestamp,
                balance=self.simulator.balance,
                equity=self.simulator.equity,
                floating_pnl=self.simulator.equity - self.simulator.balance,
                realized_pnl=0.0, # Handled per trade
                commission=0.0,
                swap=0.0,
                margin=self.simulator.margin,
                margin_free=self.simulator.equity - self.simulator.margin,
                drawdown=dd,
                daily_pnl=self.simulator.equity - self.start_of_day_equity
            )
            self.ledger.append_equity_record(er)
            
        if self.end_of_test_policy == "FLATTEN_AT_END" and data:
            # Flatten all open positions
            open_pos = [p for p in self.simulator.positions if p.state == PositionState.OPEN]
            for p in open_pos:
                closed_trade, closed_fill = self.simulator.close_position(str(p.id), reason="FLATTEN_AT_END")
                if closed_trade and closed_fill:
                    self.ledger.append_closed_trade(closed_trade)
                    from app.evaluation.ledger import ExecutionRecord
                    self.ledger.append_execution(ExecutionRecord(
                        order_id=closed_fill.order_id,
                        symbol=closed_fill.symbol,
                        side="SELL" if p.side.value == "BUY" else "BUY",
                        volume=closed_fill.volume,
                        requested_price=closed_fill.price,
                        fill_price=closed_fill.price,
                        timestamp=closed_fill.timestamp,
                        realized_pnl=closed_fill.realized_pnl,
                        commission=closed_fill.commission,
                        swap=closed_fill.swap
                    ))
            
            # Record final equity
            if open_pos:
                dd = (self.equity_peak - self.simulator.equity) / self.equity_peak if self.equity_peak > 0 else 0.0
                er = EquityRecord(
                    timestamp=data[-1].timestamp,
                    balance=self.simulator.balance,
                    equity=self.simulator.equity,
                    floating_pnl=self.simulator.equity - self.simulator.balance,
                    realized_pnl=0.0,
                    commission=0.0,
                    swap=0.0,
                    margin=self.simulator.margin,
                    margin_free=self.simulator.equity - self.simulator.margin,
                    drawdown=dd,
                    daily_pnl=self.simulator.equity - self.start_of_day_equity
                )
                self.ledger.append_equity_record(er)
                
        metrics = self.metrics_calculator.calculate(self.ledger.closed_trades, self.ledger.equity_curve, self.initial_balance)
        
        spec_data = ExperimentSpec(
            git_sha="detached", dataset_hash="none", feature_version="1", simulator_version="1",
            risk_policy_id=self.policy.id, risk_policy_version=self.policy.version,
            environment_version="1", seed=0, train_window={}, validation_window={},
            test_window={"start": data[0].timestamp, "end": data[-1].timestamp} if data else {},
            holdout_window={}, execution_cost_profile="deterministic"
        )
        
        experiment_result = ExperimentResult(
            experiment_id=str(uuid4()),
            spec=spec_data,
            hyperparameters={},
            metrics=metrics,
            artifacts=[]
        )
        
        return BacktestResult(
            experiment_result=experiment_result,
            equity_curve=self.ledger.equity_curve,
            closed_trades=self.ledger.closed_trades,
            executions=self.ledger.executions,
            risk_events=self.risk_events,
            metrics=metrics
        )
