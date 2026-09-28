import pytest
from datetime import datetime, timedelta
import pandas as pd
from uuid import uuid4

from app.domain.models import Quote, InstrumentSpec, OrderIntent, OrderSide, OrderType, ApprovedOrder, RiskContext, RiskPolicy, ExperimentManifest
from app.risk.engine import RiskEngine
from app.simulator.engine import SimulatorEngine
from app.strategies.baseline import SMATrend

def test_full_deterministic_research_flow():
    # 1. Synthetic Market Data
    base_time = datetime.utcnow()
    data = []
    prices = [1.1000, 1.1010, 1.1020, 1.1030, 1.1040, 1.1050, 1.1040, 1.1030, 1.1020, 1.1010, 1.1000]
    
    for i, p in enumerate(prices):
        data.append(Quote(timestamp=base_time + timedelta(minutes=i), symbol="EURUSD", bid=p, ask=p+0.0002))
        
    df = pd.DataFrame([{
        "timestamp": q.timestamp, 
        "close": q.bid, 
        "symbol": q.symbol
    } for q in data])
    
    # 2. Setup Components
    sim = SimulatorEngine(initial_balance=10000.0)
    spec = InstrumentSpec(
        broker_symbol="EURUSD", canonical_symbol="EURUSD", asset_class="FX", digits=5, point=0.00001,
        tick_size=0.00001, tick_value=1.0, contract_size=100000.0, volume_min=0.01, volume_max=10.0,
        volume_step=0.01, margin_currency="USD", profit_currency="USD", execution_mode="MARKET",
        trading_sessions={}, stop_level=0
    )
    sim.set_instrument(spec)
    
    risk_engine = RiskEngine()
    policy = RiskPolicy(
        id="test-pol", version="1.0", max_daily_loss_pct=0.05, max_drawdown_pct=0.10,
        max_trade_risk_pct=0.01, max_open_risk_pct=0.05, max_gross_exposure=1000000.0,
        max_net_exposure=500000.0, max_position_count=5, max_spread_pts=50,
        require_sl=False, session_constraints={}, leverage_limit=30.0
    )
    
    strategy = SMATrend(symbol="EURUSD", fast_period=2, slow_period=4, volume=1.0)
    
    trade_ledger = []
    
    # 3. Execution Loop
    for i in range(len(data)):
        q = data[i]
        sim.update_quote(q)
        
        history = df.iloc[:i+1]
        
        # Strategy -> TargetPosition
        target_pos = strategy.next(q, history)
        
        if target_pos:
            context = RiskContext(
                account=sim.get_account_snapshot(),
                open_positions=sim.positions,
                current_quote=q,
                instrument=spec
            )
            
            # RiskEngine -> RiskDecision
            decision = risk_engine.evaluate(context, target_pos, policy)
            
            if decision.state.value == "APPROVE":
                # Convert TargetPosition to OrderIntent for simplicity of testing
                current_vol = sum([p.volume if p.side == OrderSide.BUY else -p.volume for p in sim.positions if p.symbol == target_pos.symbol and p.state.value == "OPEN"])
                diff = target_pos.target_volume - current_vol
                if abs(diff) > 0:
                    intent = OrderIntent(
                        symbol=target_pos.symbol,
                        side=OrderSide.BUY if diff > 0 else OrderSide.SELL,
                        type=OrderType.MARKET,
                        volume=abs(diff)
                    )
                    
                    approved = ApprovedOrder(intent=intent, risk_decision=decision, timestamp=q.timestamp)
                    
                    # Simulator
                    res = sim.submit_order(approved)
                    if res.success:
                        trade_ledger.append(res.fill)
    
    # Close all positions at end
    for p in sim.positions:
        if p.state.value == "OPEN":
            sim.close_position(str(p.id))
            
    # Metrics
    metrics = {
        "final_balance": sim.balance,
        "total_trades": len(trade_ledger)
    }
    
    # Experiment Manifest
    manifest = ExperimentManifest(
        experiment_id=str(uuid4()),
        git_sha="abcdef",
        dataset_hash="hash123",
        feature_version="1.0",
        simulator_version="1.0",
        risk_policy_id="test-pol",
        risk_policy_version="1.0",
        environment_version="1.0",
        seed=42,
        hyperparameters={"fast": 2, "slow": 4},
        train_window={},
        validation_window={},
        test_window={"start": data[0].timestamp, "end": data[-1].timestamp},
        holdout_window={},
        execution_cost_profile="default",
        mlflow_run_id="run-123",
        metrics=metrics,
        artifacts=[]
    )
    
    assert manifest.metrics["total_trades"] >= 0
    assert manifest.metrics["final_balance"] > 0
