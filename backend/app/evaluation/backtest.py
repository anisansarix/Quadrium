from typing import Any
from uuid import uuid4

import pandas as pd

from app.core.decision_pipeline import DecisionPipeline
from app.domain.models import (
    BacktestResult,
    ExperimentResult,
    ExperimentSpec,
    InstrumentSpec,
    Quote,
    RiskContext,
    RiskDecision,
    RiskPolicy,
    SimulationEvent,
)
from app.evaluation.ledger import EquityRecord, ExecutionRecord, Ledger
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
        self.risk_events: list[RiskDecision] = []
        
        self.start_of_day_equity = simulator.equity
        self.equity_peak = simulator.equity
        self.initial_balance = simulator.balance
        
        self.prev_balance = simulator.balance
        self.prev_commission = 0.0
        self.prev_swap = 0.0

    def _process_simulation_event(self, event: SimulationEvent, quote: Quote, side_hint: str = "SELL") -> None:
        for fill in event.fills:
            self.ledger.append_execution(ExecutionRecord(
                order_id=fill.order_id,
                symbol=fill.symbol,
                side=side_hint,
                volume=fill.volume,
                requested_price=quote.ask if side_hint == "BUY" else quote.bid,
                fill_price=fill.price,
                timestamp=fill.timestamp,
                realized_pnl=fill.realized_pnl,
                commission=fill.commission,
                swap=fill.swap
            ))
        for ct in event.closed_trades:
            self.ledger.append_closed_trade(ct)
        for rd in event.risk_events:
            self.risk_events.append(rd)

    def run(self, data: list[Quote], spec: InstrumentSpec, metadata: dict[str, Any] | None = None) -> BacktestResult:
        self.simulator.set_instrument(spec)
        history_records: list[dict[str, Any]] = []
        last_date = None
        
        metadata = metadata or {}
        git_sha = metadata.get("git_sha", "unknown")
        dataset_hash = metadata.get("dataset_hash", "unknown")
        feature_version = metadata.get("feature_version", "1.0")
        simulator_version = metadata.get("simulator_version", "1.0")
        environment_version = metadata.get("environment_version", "1.0")
        seed = metadata.get("seed", 0)
        execution_cost_profile = metadata.get("execution_cost_profile", "default")
        
        for q in data:
            sim_event = self.simulator.update_quote(q)
            self._process_simulation_event(sim_event, q)
            
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
                approved_order, decision = self.pipeline.process(target, context, self.policy)
                if decision:
                    self.risk_events.append(decision)
                    
                    from app.core.decision_executor import DecisionExecutor
                    executor = DecisionExecutor(self.simulator)
                    res = executor.execute(decision, approved_order)
                    
                    if res and res.success:
                        sim_event2 = SimulationEvent(timestamp=q.timestamp, fills=res.fills, closed_trades=res.closed_trades)
                        self._process_simulation_event(sim_event2, q, side_hint=approved_order.intent.side.value if approved_order else "SELL")
                            
            # Calculate Deltas for EquityRecord
            realized_pnl_delta = self.simulator.balance - self.prev_balance
            
            # Simple approach: Since the engine charges commission dynamically, we can derive the commission delta 
            # by tracking total commission charged this tick if we had a total_commission state, but we don't.
            # Instead, we sum it from the ledger executions that match this timestamp.
            tick_execs = [e for e in self.ledger.executions if e.timestamp == q.timestamp]
            comm_delta = sum(e.commission for e in tick_execs)
            swap_delta = sum(e.swap for e in tick_execs)
            
            # In our SimulatorEngine, balance += realized_pnl - comm - swap
            # We want pure realized_pnl_delta without costs for the record:
            pure_realized_pnl_delta = realized_pnl_delta + comm_delta + swap_delta
            
            dd = (self.equity_peak - self.simulator.equity) / self.equity_peak if self.equity_peak > 0 else 0.0
            er = EquityRecord(
                timestamp=q.timestamp,
                balance=self.simulator.balance,
                equity=self.simulator.equity,
                floating_pnl=self.simulator.equity - self.simulator.balance,
                realized_pnl_delta=pure_realized_pnl_delta,
                commission_delta=comm_delta,
                swap_delta=swap_delta,
                margin=self.simulator.margin,
                margin_free=self.simulator.equity - self.simulator.margin,
                drawdown=dd,
                daily_pnl=self.simulator.equity - self.start_of_day_equity
            )
            self.ledger.append_equity_record(er)
            
            self.prev_balance = self.simulator.balance
            
        if self.end_of_test_policy == "FLATTEN_AT_END" and data:
            cts, fills = self.simulator.flatten_positions(reason="FLATTEN_AT_END")
            if cts or fills:
                self._process_simulation_event(SimulationEvent(timestamp=data[-1].timestamp, fills=fills, closed_trades=cts), data[-1])
                
                realized_pnl_delta = self.simulator.balance - self.prev_balance
                comm_delta = sum(f.commission for f in fills)
                swap_delta = sum(f.swap for f in fills)
                pure_realized_pnl_delta = realized_pnl_delta + comm_delta + swap_delta
                
                dd = (self.equity_peak - self.simulator.equity) / self.equity_peak if self.equity_peak > 0 else 0.0
                er = EquityRecord(
                    timestamp=data[-1].timestamp,
                    balance=self.simulator.balance,
                    equity=self.simulator.equity,
                    floating_pnl=self.simulator.equity - self.simulator.balance,
                    realized_pnl_delta=pure_realized_pnl_delta,
                    commission_delta=comm_delta,
                    swap_delta=swap_delta,
                    margin=self.simulator.margin,
                    margin_free=self.simulator.equity - self.simulator.margin,
                    drawdown=dd,
                    daily_pnl=self.simulator.equity - self.start_of_day_equity
                )
                self.ledger.append_equity_record(er)
                
        metrics = self.metrics_calculator.calculate(self.ledger.closed_trades, self.ledger.equity_curve, self.initial_balance)
        
        spec_data = ExperimentSpec(
            git_sha=git_sha, dataset_hash=dataset_hash, feature_version=feature_version, simulator_version=simulator_version,
            risk_policy_id=self.policy.id, risk_policy_version=self.policy.version,
            environment_version=environment_version, seed=seed, train_window={}, validation_window={},
            test_window={"start": data[0].timestamp, "end": data[-1].timestamp} if data else {},
            holdout_window={}, execution_cost_profile=execution_cost_profile
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
