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
    
    # Exact reward derivation:
    # Volume: leverage_limit (30) * equity (10000) / notional(100k * 1.1002) = 2.72
    # Open price (buy at ask): 1.1002
    # Next mark-to-market bid: 1.1010
    # Floating PnL = (1.1010 - 1.1002) * 2.72 * 100000 = 217.6
    # Final equity = 10000 + 217.6 = 10217.6
    # Reward = log(10217.6 / 10000)
    
    import numpy as np
    expected_equity = 10217.6
    expected_reward = float(np.log(expected_equity / 10000.0))
    
    assert info['equity'] == pytest.approx(expected_equity)
    assert reward == pytest.approx(expected_reward)

def test_account_state_orchestration(spec, policy):
    from app.core.decision_executor import DecisionExecutor
    sim = SimulatorEngine(initial_balance=10000.0)
    sim.set_instrument(spec)
    engine = RiskEngine()
    executor = DecisionExecutor(sim)
    
    # Base ctx
    t = datetime.now(UTC)
    q = Quote(timestamp=t, symbol="EURUSD", bid=1.1000, ask=1.1002)
    sim.update_quote(q)
    
    # Open a position first so we can verify FLATTEN closes it
    from app.domain.models import (
        ApprovedOrder,
        OrderIntent,
        OrderSide,
        OrderType,
        RiskDecision,
        RiskDecisionState,
    )
    intent = OrderIntent(symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=1.0)
    decision = RiskDecision(state=RiskDecisionState.APPROVE, proposed_target=1.0, approved_target=1.0, proposed_volume=1.0, approved_volume=1.0, policy_id="x", policy_version="1", timestamp=t)
    sim.submit_order(ApprovedOrder(intent=intent, risk_decision=decision, timestamp=t))
    assert len(sim.positions) == 1
    
    # 1. Hard drawdown breach -> FLATTEN
    policy.max_drawdown_pct = 0.10
    sim.equity = 8000.0 # 20% drawdown
    ctx = RiskContext(account=sim.get_account_snapshot(), open_positions=sim.positions, current_quote=q, instrument=spec, start_of_day_equity=10000.0, equity_peak=10000.0, current_time=t)
    decision_flatten = engine.evaluate(ctx, intent, policy, 1.0, 1.0)
    assert decision_flatten.state == RiskDecisionState.FLATTEN
    
    # Execute flatten
    executor.execute(decision_flatten)
    assert len([p for p in sim.positions if p.state.value == "OPEN"]) == 0 # closed
    assert sim.account_state == AccountState.FLATTEN_AND_FREEZE
    
    # New order rejected by simulator
    res = sim.submit_order(ApprovedOrder(intent=intent, risk_decision=decision, timestamp=t))
    assert res.success is False
    assert "frozen" in res.error_message.lower()
    
    # Reset and test FREEZE
    sim.account_state = AccountState.NORMAL
    sim.equity = 9000.0 # 10% loss
    sim.balance = 10000.0
    policy.max_drawdown_pct = 0.50 # avoid flatten
    ctx2 = RiskContext(account=sim.get_account_snapshot(), open_positions=sim.positions, current_quote=q, instrument=spec, start_of_day_equity=10000.0, equity_peak=10000.0, current_time=t)
    decision_freeze = engine.evaluate(ctx2, intent, policy, 1.0, 1.0)
    assert decision_freeze.state == RiskDecisionState.FREEZE
    
    executor.execute(decision_freeze)
    assert sim.account_state == AccountState.FREEZE
    
    res2 = sim.submit_order(ApprovedOrder(intent=intent, risk_decision=decision, timestamp=t))
    assert res2.success is False
    assert "frozen" in res2.error_message.lower()

def test_sl_reaches_ledger_end_to_end(spec, policy):
    from app.core.decision_pipeline import DecisionPipeline
    from app.domain.models import (
        ApprovedOrder,
        OrderIntent,
        OrderSide,
        OrderType,
        RiskDecision,
        RiskDecisionState,
        TargetPosition,
    )
    from app.evaluation.backtest import BacktestRunner
    from app.strategies.baseline import Strategy
    
    class MockStrategy(Strategy):
        def __init__(self):
            super().__init__()
            self.triggered = False
        def next(self, quote, history):
            if not self.triggered:
                self.triggered = True
                return TargetPosition(symbol="EURUSD", target_weight=1.0)
            return None
            
    class MockPipeline(DecisionPipeline):
        def process(self, target, context, policy):
            if target.target_weight == 0:
                return None, None
            # Buy with SL at 1.0990
            intent = OrderIntent(symbol="EURUSD", side=OrderSide.BUY, type=OrderType.MARKET, volume=1.0, sl=1.0990)
            decision = RiskDecision(state=RiskDecisionState.APPROVE, proposed_target=1.0, approved_target=1.0, proposed_volume=1.0, approved_volume=1.0, policy_id="x", policy_version="1", timestamp=context.current_time)
            return ApprovedOrder(intent=intent, risk_decision=decision, timestamp=context.current_time), decision

    sim = SimulatorEngine(initial_balance=10000.0)
    runner = BacktestRunner(sim, MockPipeline(RiskEngine()), policy, MockStrategy())
    
    t0 = datetime(2025, 1, 1, 10, 0, tzinfo=UTC)
    data = [
        Quote(timestamp=t0, symbol='EURUSD', bid=1.1000, ask=1.1002), # Buy at ask 1.1002, SL 1.0990
        Quote(timestamp=t0+timedelta(minutes=1), symbol='EURUSD', bid=1.0988, ask=1.0990), # SL trigger because bid 1.0988 <= 1.0990
        Quote(timestamp=t0+timedelta(minutes=2), symbol='EURUSD', bid=1.0980, ask=1.0982)
    ]
    
    result = runner.run(data, spec)
    
    # Assertions
    assert len(result.executions) == 2 # Entry and SL exit
    assert len(result.closed_trades) == 1
    
    ct = result.closed_trades[0]
    assert ct.exit_reason == "SL"
    
    # Check that equity curve drops
    # The exit is at 1.0988 (trigger price of BID, which is 1.0988)
    # Entry at 1.1002. Loss is 1.1002 - 1.0988 = 0.0014 * 100000 = 
    # Final equity should be 10000 - 140 = 9860
    assert result.equity_curve[-1].equity == pytest.approx(9860.0)
