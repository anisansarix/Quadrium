from datetime import UTC, datetime, timedelta

import pytest
from app.domain.models import (
    AccountSnapshot,
    AccountState,
    ApprovedOrder,
    InstrumentSpec,
    OrderIntent,
    OrderSide,
    OrderType,
    PositionState,
    Quote,
    RiskContext,
    RiskDecision,
    RiskDecisionState,
    RiskPolicy,
)
from app.risk.engine import RiskEngine
from app.simulator.engine import SimulatorEngine
from app.simulator.models.commission import FixedPerLotCommissionModel
from app.simulator.models.currency import DeterministicUSDModel
from app.simulator.models.fill_policy import IntrabarFillPolicy, SLTriggerQuote


@pytest.fixture
def spec():
    return InstrumentSpec(
        broker_symbol="EURUSD", canonical_symbol="EURUSD", asset_class="FX", digits=5, point=0.00001,
        tick_size=0.00001, tick_value=1.0, contract_size=100000.0, volume_min=0.01, volume_max=10.0,
        volume_step=0.01, margin_currency="USD", profit_currency="USD", execution_mode="MARKET",
        trading_sessions={}, stop_level=0
    )

@pytest.fixture
def policy():
    return RiskPolicy(
        id="pol-1", version="1.0", max_daily_loss_pct=0.05, max_drawdown_pct=0.10,
        max_trade_risk_pct=0.01, max_open_risk_pct=0.05, max_gross_exposure=5000000.0,
        max_net_exposure=5000000.0, max_position_count=5, max_spread_pts=50,
        require_sl=False, session_constraints={}, leverage_limit=30.0
    )

def test_unsupported_currency_conversion():
    with pytest.raises(ValueError, match="strictly requires USD account"):
        DeterministicUSDModel(account_currency="EUR")
        
    model = DeterministicUSDModel()
    with pytest.raises(ValueError, match="Unsupported source currency EUR"):
        model.convert_to_account_currency(100.0, "EUR")

def test_scenario_buy_and_price_rises(spec):
    sim = SimulatorEngine(initial_balance=10000.0)
    sim.set_instrument(spec)
    t = datetime.now(UTC)
    sim.update_quote(Quote(timestamp=t, symbol="EURUSD", bid=1.1000, ask=1.1002))
    
    intent = OrderIntent(symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=1.0)
    decision = RiskDecision(state=RiskDecisionState.APPROVE, proposed_target=1.0, approved_target=1.0, proposed_volume=1.0, approved_volume=1.0, policy_id="x", policy_version="1", timestamp=t)
    sim.submit_order(ApprovedOrder(intent=intent, risk_decision=decision, timestamp=t))
    
    assert sim.balance == 10000.0 # No commission yet
    
    # price rises
    sim.update_quote(Quote(timestamp=t, symbol="EURUSD", bid=1.1010, ask=1.1012))
    
    assert sim.equity == pytest.approx(10080.0) # (1.1010 - 1.1002) * 100000 = 80
    assert len(sim.positions) == 1

def test_scenario_sell_and_price_falls(spec):
    sim = SimulatorEngine(initial_balance=10000.0)
    sim.set_instrument(spec)
    t = datetime.now(UTC)
    sim.update_quote(Quote(timestamp=t, symbol="EURUSD", bid=1.1000, ask=1.1002))
    
    intent = OrderIntent(symbol="EURUSD", side=OrderSide.SELL, type=OrderType.MARKET, volume=1.0)
    decision = RiskDecision(state=RiskDecisionState.APPROVE, proposed_target=-1.0, approved_target=-1.0, proposed_volume=1.0, approved_volume=1.0, policy_id="x", policy_version="1", timestamp=t)
    sim.submit_order(ApprovedOrder(intent=intent, risk_decision=decision, timestamp=t))
    
    # price falls
    sim.update_quote(Quote(timestamp=t, symbol="EURUSD", bid=1.0990, ask=1.0992))
    
    assert sim.equity == pytest.approx(10080.0) # (1.1000 - 1.0992) * 100000 = 80
    
def test_scenario_spread_only_loss(spec):
    sim = SimulatorEngine(initial_balance=10000.0)
    sim.set_instrument(spec)
    t = datetime.now(UTC)
    sim.update_quote(Quote(timestamp=t, symbol="EURUSD", bid=1.1000, ask=1.1002))
    
    intent = OrderIntent(symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=1.0)
    decision = RiskDecision(state=RiskDecisionState.APPROVE, proposed_target=1.0, approved_target=1.0, proposed_volume=1.0, approved_volume=1.0, policy_id="x", policy_version="1", timestamp=t)
    sim.submit_order(ApprovedOrder(intent=intent, risk_decision=decision, timestamp=t))
    
    assert sim.balance == 10000.0
    assert sim.equity == pytest.approx(9980.0) # 2 pips spread on 1 lot = $20 loss unrealized

def test_scenario_commission_exactly_once(spec):
    sim = SimulatorEngine(initial_balance=10000.0, commission_model=FixedPerLotCommissionModel(3.0))
    sim.set_instrument(spec)
    t = datetime.now(UTC)
    sim.update_quote(Quote(timestamp=t, symbol="EURUSD", bid=1.1000, ask=1.1002))
    
    intent = OrderIntent(symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=1.0)
    decision = RiskDecision(state=RiskDecisionState.APPROVE, proposed_target=1.0, approved_target=1.0, proposed_volume=1.0, approved_volume=1.0, policy_id="x", policy_version="1", timestamp=t)
    sim.submit_order(ApprovedOrder(intent=intent, risk_decision=decision, timestamp=t))
    
    assert sim.balance == 9997.0 # $3 comm realized
    assert sim.equity == pytest.approx(9977.0) # $3 comm + $20 spread loss
    
    # Close
    sim.close_position(str(sim.positions[0].id))
    
    assert sim.balance == pytest.approx(9974.0)
    assert sim.equity == pytest.approx(9974.0) # Commission wasn't double counted

def test_scenario_partial_close_and_reversal(spec, policy):
    sim = SimulatorEngine(initial_balance=10000.0)
    sim.set_instrument(spec)
    t = datetime.now(UTC)
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
    assert sim.balance == pytest.approx(9980.0) # 1 lot realized spread loss
    
    # Sell 2 lots -> Reversal (closes remaining 1 lot, opens 1 lot short)
    intent3 = OrderIntent(symbol="EURUSD", side=OrderSide.SELL, type=OrderType.MARKET, volume=2.0)
    res = sim.submit_order(ApprovedOrder(intent=intent3, risk_decision=decision, timestamp=t))
    
    open_pos = [p for p in sim.positions if p.state == PositionState.OPEN]
    assert len(open_pos) == 1
    assert open_pos[0].side == OrderSide.SELL
    assert open_pos[0].volume == 1.0
    assert len(res.closed_trades) == 1
    assert res.closed_trades[0].exit_volume == 1.0

def test_scenario_risk_breaches(spec, policy):
    engine = RiskEngine()
    
    # Base ctx
    t = datetime.now(UTC)
    q = Quote(timestamp=t, symbol="EURUSD", bid=1.1000, ask=1.1002)
    acc = AccountSnapshot(timestamp=t, balance=10000, equity=10000, margin=0, margin_free=10000, margin_level=100, currency="USD", state=AccountState.NORMAL)
    ctx = RiskContext(account=acc, open_positions=[], current_quote=q, instrument=spec, start_of_day_equity=10000.0, equity_peak=10000.0, current_time=t)
    
    intent = OrderIntent(symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=5.0)
    
    # 1. Leverage clamp
    decision = engine.evaluate(ctx, intent, policy, 1.0, 5.0)
    assert decision.state == RiskDecisionState.CLAMP
    assert decision.approved_volume == pytest.approx(2.72) # (10000 * 30) / (1.1002 * 100000) = 2.726 => floor => 2.72
    
    # 2. Drawdown breach
    ctx.account.equity = 8000.0 # 20% drawdown
    decision2 = engine.evaluate(ctx, intent, policy, 1.0, 5.0)
    assert decision2.state == RiskDecisionState.FLATTEN
    
    # 3. Daily loss breach
    policy.max_drawdown_pct = 0.50
    ctx.account.equity = 9000.0 # 10% daily loss
    decision3 = engine.evaluate(ctx, intent, policy, 1.0, 5.0)
    assert decision3.state == RiskDecisionState.FREEZE

def test_scenario_sl_tp_close(spec):
    sim = SimulatorEngine(initial_balance=10000.0, fill_policy=IntrabarFillPolicy(long_sl_trigger=SLTriggerQuote.BID, long_tp_trigger=SLTriggerQuote.BID))
    sim.set_instrument(spec)
    t = datetime.now(UTC)
    sim.update_quote(Quote(timestamp=t, symbol="EURUSD", bid=1.1000, ask=1.1002))
    
    intent = OrderIntent(symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=1.0, sl=1.0900, tp=1.1100)
    decision = RiskDecision(state=RiskDecisionState.APPROVE, proposed_target=1.0, approved_target=1.0, proposed_volume=1.0, approved_volume=1.0, policy_id="x", policy_version="1", timestamp=t)
    sim.submit_order(ApprovedOrder(intent=intent, risk_decision=decision, timestamp=t))
    
    # Hit SL
    sim.update_quote(Quote(timestamp=t, symbol="EURUSD", bid=1.0900, ask=1.0902))
    open_pos = [p for p in sim.positions if p.state == PositionState.OPEN]
    assert len(open_pos) == 0
    assert sim.balance == pytest.approx(8980.0) # (1.0900 - 1.1002) * 100k = -1020

def test_golden_accounting_regression(spec):
    sim = SimulatorEngine(initial_balance=10000.0, commission_model=FixedPerLotCommissionModel(3.0))
    sim.set_instrument(spec)
    
    t0 = datetime(2025, 1, 1, 10, 0, tzinfo=UTC)
    sim.update_quote(Quote(timestamp=t0, symbol='EURUSD', bid=1.1000, ask=1.1002))
    
    intent = OrderIntent(symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=1.0)
    decision = RiskDecision(state=RiskDecisionState.APPROVE, proposed_target=1.0, approved_target=1.0, proposed_volume=1.0, approved_volume=1.0, policy_id="x", policy_version="1", timestamp=t0)
    sim.submit_order(ApprovedOrder(intent=intent, risk_decision=decision, timestamp=t0))
    
    # Assert Entry
    assert sim.balance == 9997.0 # 3.0 entry commission deducted
    assert sim.equity == pytest.approx(9977.0) # 9997 + (1.1000 - 1.1002)*100k
    
    t1 = datetime(2025, 1, 1, 11, 0, tzinfo=UTC)
    sim.update_quote(Quote(timestamp=t1, symbol='EURUSD', bid=1.1010, ask=1.1012))
    
    assert sim.equity == pytest.approx(10077.0) # 9997 + (1.1010 - 1.1002)*100k = 9997 + 80
    
    ct, f = sim.close_position(str(sim.positions[0].id))
    
    # Exit metrics
    assert f.price == 1.1010
    assert f.commission == 3.0 # Exit comm
    assert ct.entry_commission == 3.0
    assert ct.exit_commission == 3.0
    assert ct.gross_pnl == pytest.approx(80.0)
    assert ct.net_pnl == pytest.approx(74.0)
    
    # Final Balance
    assert sim.balance == pytest.approx(10074.0) # 10000 - 3(in) + 80(pnl) - 3(out)
    assert sim.equity == pytest.approx(10074.0)

def test_risk_inclusive_bounds(spec, policy):
    engine = RiskEngine()
    t = datetime.now(UTC)
    q = Quote(timestamp=t, symbol="EURUSD", bid=1.1000, ask=1.1002)
    acc = AccountSnapshot(timestamp=t, balance=10000, equity=10000, margin=0, margin_free=10000, margin_level=100, currency="USD", state=AccountState.NORMAL)
    ctx = RiskContext(account=acc, open_positions=[], current_quote=q, instrument=spec, start_of_day_equity=10000.0, equity_peak=10000.0, current_time=t)
    
    # Limit exactly hit
    ctx.account.equity = 9000.0 # Exactly 10% drawdown
    policy.max_drawdown_pct = 0.10
    intent = OrderIntent(symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=1.0)
    decision = engine.evaluate(ctx, intent, policy, 1.0, 1.0)
    assert decision.state == RiskDecisionState.FLATTEN
    
    ctx.account.equity = 9000.001 # Slightly less than 10%
    decision = engine.evaluate(ctx, intent, policy, 1.0, 1.0)
    assert decision.state != RiskDecisionState.FLATTEN

def test_exposure_reduction_bypasses_limits(spec, policy):
    engine = RiskEngine()
    t = datetime.now(UTC)
    q = Quote(timestamp=t, symbol="EURUSD", bid=1.1000, ask=1.1002)
    acc = AccountSnapshot(timestamp=t, balance=10000, equity=10000, margin=0, margin_free=10000, margin_level=100, currency="USD", state=AccountState.NORMAL)
    
    # Create existing open position of 5 lots
    from uuid import uuid4

    from app.domain.models import Position
    pos = Position(id=uuid4(), symbol="EURUSD", side=OrderSide.BUY, volume=5.0, open_price=1.1002, open_timestamp=t, state=PositionState.OPEN, commission=0)
    
    ctx = RiskContext(account=acc, open_positions=[pos], current_quote=q, instrument=spec, start_of_day_equity=10000.0, equity_peak=10000.0, current_time=t)
    
    # Intent: Sell 2 lots (reduce exposure)
    intent = OrderIntent(symbol="EURUSD", side=OrderSide.SELL, type=OrderType.MARKET, volume=2.0)
    
    # Even if max net exposure is tiny, reducing exposure should be approved
    policy.max_net_exposure = 1.0 
    decision = engine.evaluate(ctx, intent, policy, -1.0, 2.0)
    assert decision.state == RiskDecisionState.APPROVE

def test_gym_reward_transition(spec, policy):
    from app.core.decision_pipeline import DecisionPipeline
    from app.envs.trading import TradingEnv
    from app.simulator.engine import SimulatorEngine
    
    sim = SimulatorEngine(initial_balance=10000.0)
    sim.set_instrument(spec)
    pipeline = DecisionPipeline(RiskEngine())
    
    t = datetime(2025, 1, 1, 10, 0, tzinfo=UTC)
    data = [
        Quote(timestamp=t, symbol='EURUSD', bid=1.1000, ask=1.1002),
        Quote(timestamp=t+timedelta(minutes=1), symbol='EURUSD', bid=1.1010, ask=1.1012),
        Quote(timestamp=t+timedelta(minutes=2), symbol='EURUSD', bid=1.1020, ask=1.1022)
    ]
    
    env = TradingEnv(simulator=sim, pipeline=pipeline, policy=policy, data=data)
    env.reset()
    
    _obs, reward, _terminated, _truncated, info = env.step([1.0])
    
    # t=0 action is buy. Price moves from 1.1002 (ask) to 1.1010 (bid at t=1).
    # Contract size 100k, Volume is based on max net exposure.
    # We just want to check that reward > 0 and info equity > 10000
    
        
    assert reward > 0
    assert info['equity'] > 10000
