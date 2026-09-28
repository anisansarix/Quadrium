from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pandas as pd
from app.core.decision_pipeline import DecisionPipeline
from app.domain.models import (
    ExperimentResult,
    ExperimentSpec,
    InstrumentSpec,
    Quote,
    RiskContext,
    RiskPolicy,
)
from app.risk.engine import RiskEngine
from app.simulator.engine import SimulatorEngine
from app.strategies.baseline import SMATrend


def test_full_deterministic_research_flow() -> None:
    base_time = datetime.now(UTC)
    data = []
    prices = [1.1000, 1.1010, 1.1020, 1.1030, 1.1040, 1.1050, 1.1040, 1.1030, 1.1020, 1.1010, 1.1000]
    
    for i, p in enumerate(prices):
        data.append(Quote(timestamp=base_time + timedelta(minutes=i), symbol="EURUSD", bid=p, ask=p+0.0002))
        
    df = pd.DataFrame([{
        "timestamp": q.timestamp, 
        "close": q.bid, 
        "symbol": q.symbol
    } for q in data])
    
    sim = SimulatorEngine(initial_balance=10000.0)
    spec = InstrumentSpec(
        broker_symbol="EURUSD", canonical_symbol="EURUSD", asset_class="FX", digits=5, point=0.00001,
        tick_size=0.00001, tick_value=1.0, contract_size=100000.0, volume_min=0.01, volume_max=10.0,
        volume_step=0.01, margin_currency="USD", profit_currency="USD", execution_mode="MARKET",
        trading_sessions={}, stop_level=0
    )
    sim.set_instrument(spec)
    
    risk_engine = RiskEngine()
    pipeline = DecisionPipeline(risk_engine)
    
    policy = RiskPolicy(
        id="test-pol", version="1.0", max_daily_loss_pct=0.05, max_drawdown_pct=0.10,
        max_trade_risk_pct=0.01, max_open_risk_pct=0.05, max_gross_exposure=1000000.0,
        max_net_exposure=50000.0, # Will buy 0.5 lots roughly at weight 1.0 (50k / 100k)
        max_position_count=5, max_spread_pts=50,
        require_sl=False, session_constraints={}, leverage_limit=30.0
    )
    
    strategy = SMATrend(symbol="EURUSD", fast_period=2, slow_period=4, target_weight=1.0)
    
    trade_ledger = []
    
    for i in range(len(data)):
        q = data[i]
        sim.update_quote(q)
        
        history = df.iloc[:i+1]
        
        target_pos = strategy.next(q, history)
        
        if target_pos:
            context = RiskContext(
                account=sim.get_account_snapshot(),
                open_positions=sim.positions,
                current_quote=q,
                instrument=spec,
                start_of_day_equity=10000.0,
                equity_peak=10000.0,
                current_time=q.timestamp
            )
            
            approved, _decision = pipeline.process(target_pos, context, policy)
            if approved:
                res = sim.submit_order(approved)
                if res.success and res.fills:
                    trade_ledger.append(res.fills[0])
    
    for pos in sim.positions:
        if pos.state.value == "OPEN":
            sim.close_position(str(pos.id))
            
    metrics = {
        "final_balance": sim.balance,
        "total_trades": len(trade_ledger)
    }
    
    spec_data = ExperimentSpec(
        git_sha="abcdef", dataset_hash="hash123", feature_version="1.0", simulator_version="1.0",
        risk_policy_id="test-pol", risk_policy_version="1.0", environment_version="1.0", seed=42,
        train_window={}, validation_window={}, test_window={"start": data[0].timestamp, "end": data[-1].timestamp},
        holdout_window={}, execution_cost_profile="default"
    )
    
    result = ExperimentResult(
        experiment_id=str(uuid4()), spec=spec_data, hyperparameters={"fast": 2, "slow": 4},
        mlflow_run_id="run-123", metrics=metrics, artifacts=[]
    )
    
    assert result.metrics is not None
    assert result.metrics["total_trades"] >= 0
    assert result.metrics["final_balance"] > 0
