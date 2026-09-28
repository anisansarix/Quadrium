from datetime import UTC, datetime

import pytest
from app.domain.models import (
    ApprovedOrder,
    InstrumentSpec,
    OrderIntent,
    OrderSide,
    OrderType,
    Quote,
    RiskDecision,
    RiskDecisionState,
)
from app.simulator.engine import SimulatorEngine


@pytest.fixture
def sim():
    engine = SimulatorEngine(initial_balance=10000.0)
    spec = InstrumentSpec(
        broker_symbol="EURUSD", canonical_symbol="EURUSD", asset_class="FX", digits=5, point=0.00001,
        tick_size=0.00001, tick_value=1.0, contract_size=100000.0, volume_min=0.01, volume_max=10.0,
        volume_step=0.01, margin_currency="USD", profit_currency="USD", execution_mode="MARKET",
        trading_sessions={}, stop_level=0
    )
    engine.set_instrument(spec)
    return engine

def test_deterministic_pnl(sim):
    t1 = datetime.now(UTC)
    sim.update_quote(Quote(timestamp=t1, symbol="EURUSD", bid=1.1000, ask=1.1002))
    
    intent = OrderIntent(symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=1.0)
    decision = RiskDecision(state=RiskDecisionState.APPROVE, proposed_target=1.0, approved_target=1.0, proposed_volume=1.0, approved_volume=1.0, policy_id="x", policy_version="1", timestamp=t1)
    order = ApprovedOrder(intent=intent, risk_decision=decision, timestamp=t1)
    
    res = sim.submit_order(order)
    assert res.success
    assert len(sim.positions) == 1
    
    assert sim.equity == pytest.approx(9980.0)
    
    t2 = datetime.now(UTC)
    sim.update_quote(Quote(timestamp=t2, symbol="EURUSD", bid=1.1010, ask=1.1012))
    assert sim.equity == pytest.approx(10080.0)
    
    sim.close_position(str(sim.positions[0].id))
    assert sim.balance == pytest.approx(10080.0)

def test_simulator_reduce_and_netting(sim):
    t1 = datetime.now(UTC)
    sim.update_quote(Quote(timestamp=t1, symbol="EURUSD", bid=1.1000, ask=1.1002))
    
    intent = OrderIntent(symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=2.0)
    decision = RiskDecision(state=RiskDecisionState.APPROVE, proposed_target=1.0, approved_target=1.0, proposed_volume=2.0, approved_volume=2.0, policy_id="x", policy_version="1", timestamp=t1)
    order = ApprovedOrder(intent=intent, risk_decision=decision, timestamp=t1)
    sim.submit_order(order)
    
    # Send a sell order of 1.0. This should reduce the existing position instead of opening a new one.
    intent2 = OrderIntent(symbol="EURUSD", side=OrderSide.SELL, type=OrderType.MARKET, volume=1.0)
    order2 = ApprovedOrder(intent=intent2, risk_decision=decision, timestamp=t1)
    res = sim.submit_order(order2)
    
    assert res.success
    # Should still only be 1 position, but volume is 1.0
    assert len(sim.positions) == 1
    assert sim.positions[0].volume == 1.0
    # Realized loss from spread on 1 lot: -20
    assert sim.balance == pytest.approx(9980.0)

def test_simulator_sl_trigger(sim):
    t1 = datetime.now(UTC)
    sim.update_quote(Quote(timestamp=t1, symbol="EURUSD", bid=1.1000, ask=1.1002))
    
    intent = OrderIntent(symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=1.0, sl=1.0990)
    decision = RiskDecision(state=RiskDecisionState.APPROVE, proposed_target=1.0, approved_target=1.0, proposed_volume=1.0, approved_volume=1.0, policy_id="x", policy_version="1", timestamp=t1)
    order = ApprovedOrder(intent=intent, risk_decision=decision, timestamp=t1)
    sim.submit_order(order)
    
    assert sim.positions[0].state.value == "OPEN"
    
    # Price hits SL
    t2 = datetime.now(UTC)
    sim.update_quote(Quote(timestamp=t2, symbol="EURUSD", bid=1.0989, ask=1.0991))
    
    assert sim.positions[0].state.value == "CLOSED"
    assert sim.positions[0].close_price == 1.0989
