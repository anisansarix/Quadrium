import pytest
from datetime import datetime
from app.domain.models import RiskContext, RiskPolicy, OrderIntent, TargetPosition, OrderSide, OrderType, AccountSnapshot, Quote, InstrumentSpec, RiskDecisionState
from app.risk.engine import RiskEngine

@pytest.fixture
def base_context():
    return RiskContext(
        account=AccountSnapshot(
            timestamp=datetime.utcnow(),
            balance=10000.0,
            equity=10000.0,
            margin=0.0,
            margin_free=10000.0,
            margin_level=100.0,
            currency="USD"
        ),
        open_positions=[],
        current_quote=Quote(timestamp=datetime.utcnow(), symbol="EURUSD", bid=1.1000, ask=1.1002),
        instrument=InstrumentSpec(
            broker_symbol="EURUSD", canonical_symbol="EURUSD", asset_class="FX", digits=5, point=0.00001,
            tick_size=0.00001, tick_value=1.0, contract_size=100000.0, volume_min=0.01, volume_max=10.0,
            volume_step=0.01, margin_currency="USD", profit_currency="USD", execution_mode="MARKET",
            trading_sessions={}, stop_level=0
        )
    )

@pytest.fixture
def base_policy():
    return RiskPolicy(
        id="pol-1",
        version="1.0",
        max_daily_loss_pct=0.05,
        max_drawdown_pct=0.10,
        max_trade_risk_pct=0.01,
        max_open_risk_pct=0.05,
        max_gross_exposure=1000000.0,
        max_net_exposure=500000.0,
        max_position_count=5,
        max_spread_pts=50,
        require_sl=False,
        session_constraints={},
        leverage_limit=30.0
    )

def test_risk_approve(base_context, base_policy):
    engine = RiskEngine()
    intent = OrderIntent(symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=1.0)
    decision = engine.evaluate(base_context, intent, base_policy)
    assert decision.state == RiskDecisionState.APPROVE

def test_risk_spread_rejection(base_context, base_policy):
    engine = RiskEngine()
    # High spread quote
    base_context.current_quote = Quote(timestamp=datetime.utcnow(), symbol="EURUSD", bid=1.1000, ask=1.1010) # 100 points
    intent = OrderIntent(symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=1.0)
    decision = engine.evaluate(base_context, intent, base_policy)
    assert decision.state == RiskDecisionState.REJECT
    assert "Spread too high" in decision.reason

def test_risk_clamp_volume(base_context, base_policy):
    engine = RiskEngine()
    intent = OrderIntent(symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=15.0) # max is 10.0
    decision = engine.evaluate(base_context, intent, base_policy)
    assert decision.state == RiskDecisionState.CLAMP
    assert decision.clamped_volume == 10.0

def test_risk_require_sl(base_context, base_policy):
    base_policy.require_sl = True
    engine = RiskEngine()
    intent = OrderIntent(symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=1.0) # no SL
    decision = engine.evaluate(base_context, intent, base_policy)
    assert decision.state == RiskDecisionState.REJECT
    assert "SL is required" in decision.reason

def test_risk_drawdown_rejection(base_context, base_policy):
    base_context.account.equity = 8000.0 # 20% drawdown
    engine = RiskEngine()
    intent = TargetPosition(symbol="EURUSD", target_volume=1.0)
    decision = engine.evaluate(base_context, intent, base_policy)
    assert decision.state == RiskDecisionState.REJECT
    assert "Max drawdown exceeded" in decision.reason
