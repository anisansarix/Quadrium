import pytest
from datetime import datetime, timezone, timedelta
from app.simulator.engine import SimulatorEngine
from app.domain.models import Quote, InstrumentSpec, OrderIntent, OrderSide, OrderType, ApprovedOrder, RiskDecision, RiskDecisionState, TargetPosition, RiskContext, RiskPolicy, AccountSnapshot, PositionState
from app.core.decision_pipeline import DecisionPipeline
from app.risk.engine import RiskEngine
from app.simulator.models.currency import DeterministicUSDModel

@pytest.fixture
def spec():
    return InstrumentSpec(
        broker_symbol="EURUSD", canonical_symbol="EURUSD", asset_class="FX", digits=5, point=0.00001,
        tick_size=0.00001, tick_value=1.0, contract_size=100000.0, volume_min=0.01, volume_max=10.0,
        volume_step=0.01, margin_currency="USD", profit_currency="USD", execution_mode="MARKET",
        trading_sessions={}, stop_level=0
    )

@pytest.fixture
def sim(spec):
    engine = SimulatorEngine(initial_balance=10000.0)
    engine.set_instrument(spec)
    return engine

@pytest.fixture
def policy():
    return RiskPolicy(
        id="pol-1", version="1.0", max_daily_loss_pct=0.05, max_drawdown_pct=0.10,
        max_trade_risk_pct=0.01, max_open_risk_pct=0.05, max_gross_exposure=1000000.0,
        max_net_exposure=50000.0, max_position_count=5, max_spread_pts=50,
        require_sl=False, session_constraints={}, leverage_limit=30.0
    )

def test_unsupported_currency_conversion():
    with pytest.raises(ValueError, match="strictly requires USD account"):
        DeterministicUSDModel(account_currency="EUR")
        
    model = DeterministicUSDModel()
    with pytest.raises(ValueError, match="Unsupported source currency EUR"):
        model.convert_to_account_currency(100.0, "EUR")

def test_scenario_buy_and_price_rises(sim):
    t = datetime.now(timezone.utc)
    sim.update_quote(Quote(timestamp=t, symbol="EURUSD", bid=1.1000, ask=1.1002))
    
    intent = OrderIntent(symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=1.0)
    decision = RiskDecision(state=RiskDecisionState.APPROVE, proposed_target=1.0, approved_target=1.0, proposed_volume=1.0, approved_volume=1.0, policy_id="x", policy_version="1", timestamp=t)
    sim.submit_order(ApprovedOrder(intent=intent, risk_decision=decision, timestamp=t))
    
    # price rises
    sim.update_quote(Quote(timestamp=t, symbol="EURUSD", bid=1.1010, ask=1.1012))
    
    assert sim.equity > 10000.0
    assert len(sim.positions) == 1
    
def test_scenario_spread_only_loss(sim):
    t = datetime.now(timezone.utc)
    sim.update_quote(Quote(timestamp=t, symbol="EURUSD", bid=1.1000, ask=1.1002))
    
    intent = OrderIntent(symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=1.0)
    decision = RiskDecision(state=RiskDecisionState.APPROVE, proposed_target=1.0, approved_target=1.0, proposed_volume=1.0, approved_volume=1.0, policy_id="x", policy_version="1", timestamp=t)
    sim.submit_order(ApprovedOrder(intent=intent, risk_decision=decision, timestamp=t))
    
    assert sim.balance == 10000.0
    assert sim.equity == pytest.approx(9980.0) # 2 pips spread on 1 lot = $20 loss unrealized

def test_scenario_partial_close_and_reversal(sim, policy):
    t = datetime.now(timezone.utc)
    sim.update_quote(Quote(timestamp=t, symbol="EURUSD", bid=1.1000, ask=1.1002))
    
    intent = OrderIntent(symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=2.0)
    decision = RiskDecision(state=RiskDecisionState.APPROVE, proposed_target=1.0, approved_target=1.0, proposed_volume=2.0, approved_volume=2.0, policy_id="x", policy_version="1", timestamp=t)
    sim.submit_order(ApprovedOrder(intent=intent, risk_decision=decision, timestamp=t))
    
    # Sell 1 lot -> Partial close
    intent2 = OrderIntent(symbol="EURUSD", side=OrderSide.SELL, type=OrderType.MARKET, volume=1.0)
    sim.submit_order(ApprovedOrder(intent=intent2, risk_decision=decision, timestamp=t))
    
    open_pos = [p for p in sim.positions if p.state == PositionState.OPEN]
    assert len(open_pos) == 1
    assert open_pos[0].volume == 1.0
    assert sim.balance < 10000.0 # Realized spread loss
    
    # Sell 2 lots -> Reversal (closes remaining 1 lot, opens 1 lot short)
    intent3 = OrderIntent(symbol="EURUSD", side=OrderSide.SELL, type=OrderType.MARKET, volume=2.0)
    sim.submit_order(ApprovedOrder(intent=intent3, risk_decision=decision, timestamp=t))
    
    open_pos = [p for p in sim.positions if p.state == PositionState.OPEN]
    assert len(open_pos) == 1
    assert open_pos[0].side == OrderSide.SELL
    assert open_pos[0].volume == 1.0

def test_scenario_risk_breaches(sim, policy, spec):
    engine = RiskEngine()
    pipeline = DecisionPipeline(engine)
    
    t = datetime.now(timezone.utc)
    sim.update_quote(Quote(timestamp=t, symbol="EURUSD", bid=1.1000, ask=1.1002))
    
    ctx = RiskContext(
        account=sim.get_account_snapshot(), open_positions=sim.positions,
        current_quote=sim.quotes["EURUSD"], instrument=spec,
        start_of_day_equity=10000.0, equity_peak=10000.0, current_time=t
    )
    
    # 1. Max exposure clamp (Leverage 30, max notional 300k, so ~2.72 lots)
    target = TargetPosition(symbol="EURUSD", target_weight=1.0)
    # The pipeline calculates volume based on max_net_exposure = 50,000. 
    # Notional target = 50,000. price = 1.1002. contract = 100,000.
    # Volume = 50,000 / 110020 = 0.45 lots.
    order = pipeline.process(target, ctx, policy)
    assert order is not None
    assert order.intent.volume == 0.45
    
    # 2. Drawdown breach
    ctx.equity_peak = 10000.0
    ctx.account.equity = 8000.0 # 20% drawdown, policy max is 10%
    order2 = pipeline.process(target, ctx, policy)
    assert order2 is None # pipeline returns None if rejected by RiskEngine
