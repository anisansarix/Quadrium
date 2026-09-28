from typing import List, Dict, Any, Type
import pandas as pd
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.models import Quote, RiskContext, RiskPolicy, ExperimentSpec, ExperimentResult, InstrumentSpec
from app.simulator.engine import SimulatorEngine
from app.core.decision_pipeline import DecisionPipeline
from app.strategies.baseline import Strategy
from app.evaluation.ledger import Ledger, TradeRecord
from app.evaluation.metrics import MetricsCalculator

class BacktestRunner:
    def __init__(self, simulator: SimulatorEngine, pipeline: DecisionPipeline, policy: RiskPolicy, strategy: Strategy):
        self.simulator = simulator
        self.pipeline = pipeline
        self.policy = policy
        self.strategy = strategy
        self.ledger = Ledger()
        self.metrics_calculator = MetricsCalculator()
        
        self.start_of_day_equity = simulator.equity
        self.equity_peak = simulator.equity

    def run(self, data: List[Quote], spec: InstrumentSpec) -> ExperimentResult:
        self.simulator.set_instrument(spec)
        
        history_records = []
        
        for q in data:
            self.simulator.update_quote(q)
            history_records.append({
                "timestamp": q.timestamp,
                "close": q.bid, # Simplified OHLC history
                "symbol": q.symbol
            })
            
            self.equity_peak = max(self.equity_peak, self.simulator.equity)
            
            # Simple daily reset logic approximation
            if len(history_records) > 1 and history_records[-1]["timestamp"].date() != history_records[-2]["timestamp"].date():
                self.start_of_day_equity = self.simulator.equity
            
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
                    res = self.simulator.submit_order(approved)
                    if res.success and res.fill:
                        # Re-calculate DD based on latest equity
                        dd = (self.equity_peak - self.simulator.equity) / self.equity_peak if self.equity_peak > 0 else 0.0
                        
                        tr = TradeRecord(
                            id=uuid4(),
                            timestamp=q.timestamp,
                            symbol=res.fill.symbol,
                            side=approved.intent.side.value,
                            volume=res.fill.volume,
                            requested_price=q.ask if approved.intent.side.value == "BUY" else q.bid,
                            fill_price=res.fill.price,
                            sl=approved.intent.sl,
                            tp=approved.intent.tp,
                            commission=res.fill.commission,
                            swap=res.fill.swap,
                            realized_pnl=0.0, # Will be updated on close in a fuller ledger, or simplified here
                            unrealized_pnl=0.0,
                            balance=self.simulator.balance,
                            equity=self.simulator.equity,
                            drawdown=dd,
                            risk_decision=approved.risk_decision.state.value,
                            risk_policy_version=self.policy.version
                        )
                        self.ledger.append(tr)
                        
        metrics = self.metrics_calculator.calculate(self.ledger.trades, 10000.0) # Assume 10k start
        
        # Build ExperimentResult
        spec_data = ExperimentSpec(
            git_sha="detached", dataset_hash="none", feature_version="1", simulator_version="1",
            risk_policy_id=self.policy.id, risk_policy_version=self.policy.version,
            environment_version="1", seed=0, train_window={}, validation_window={},
            test_window={"start": data[0].timestamp, "end": data[-1].timestamp} if data else {},
            holdout_window={}, execution_cost_profile="deterministic"
        )
        
        return ExperimentResult(
            experiment_id=str(uuid4()),
            spec=spec_data,
            hyperparameters={},
            metrics=metrics,
            artifacts=[]
        )
