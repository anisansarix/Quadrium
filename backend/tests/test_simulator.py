import pytest
from datetime import datetime
from uuid import uuid4
from app.simulator.engine import SimulatorEngine
from app.domain.models import Quote, InstrumentSpec, OrderIntent, OrderSide, OrderType, ApprovedOrder, RiskDecision, RiskDecisionState

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
    sim.update_quote(Quote(timestamp=datetime.utcnow(), symbol="EURUSD", bid=1.1000, ask=1.1002))
    
    intent = OrderIntent(symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=1.0)
    order = ApprovedOrder(intent=intent, risk_decision=RiskDecision(state=RiskDecisionState.APPROVE), timestamp=datetime.utcnow())
    
    res = sim.submit_order(order)
    assert res.success
    assert len(sim.positions) == 1
    
    # Spread is 2 pips (0.0002). Buying at ask (1.1002). Current bid is 1.1000.
    # Unrealized PnL = (1.1000 - 1.1002) * 1.0 * 100000 = -20.0
    assert sim.equity == pytest.approx(9980.0)
    
    # Price moves in favor
    sim.update_quote(Quote(timestamp=datetime.utcnow(), symbol="EURUSD", bid=1.1010, ask=1.1012))
    # Unrealized PnL = (1.1010 - 1.1002) * 1.0 * 100000 = +80.0
    assert sim.equity == pytest.approx(10080.0)
    
    # Close position
    pos_id = str(sim.positions[0].id)
    sim.close_position(pos_id)
    assert sim.balance == pytest.approx(10080.0)
