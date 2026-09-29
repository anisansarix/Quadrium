from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest
from app.domain.models import FeatureState
from app.simulator.domain import ActionProposal
from app.simulator.policy_sim import PolicySimulator, TransactionCostModel


def create_mock_row(ts: datetime, open_p: float, close_p: float, spread: float = 2.0, state: FeatureState = FeatureState.VALID):
    return pd.Series({
        'timestamp': ts,
        'open': open_p,
        'high': max(open_p, close_p) + 0.0001,
        'low': min(open_p, close_p) - 0.0001,
        'close': close_p,
        'spread': spread,
        'feature_state': state,
        'ret_1': 0.01
    })

def test_flat_to_long_to_flat():
    sim = PolicySimulator(initial_balance=10000.0, symbol="EURUSD", cost_model=TransactionCostModel(point_value=0.00001, contract_size=100000.0, commission_per_unit=1.0, slippage_points=1.0))
    t1 = datetime(2026,1,1, tzinfo=UTC)

    act1 = ActionProposal(symbol="EURUSD", target_weight=1.0)
    row1 = create_mock_row(t1, 1.1000, 1.1010, spread=2.0)
    res1 = sim.process_step(act1, row1, next_obs_time=t1 + timedelta(minutes=1))

    assert len(res1.fills) == 1
    assert res1.fills[0].side.value == "BUY"
    assert res1.fills[0].price == pytest.approx(1.10003)
    assert res1.fills[0].commission == pytest.approx(1.0)
    assert sim.position.volume == 1.0

    assert sim.balance == pytest.approx(9999.0)
    assert res1.portfolio.unrealized_pnl == pytest.approx(97.0)
    assert res1.portfolio.equity == pytest.approx(10096.0)

    t2 = t1 + timedelta(minutes=1)
    act2 = ActionProposal(symbol="EURUSD", target_weight=0.0)
    row2 = create_mock_row(t2, 1.1015, 1.1020, spread=2.0)
    res2 = sim.process_step(act2, row2, next_obs_time=t2 + timedelta(minutes=1))

    assert len(res2.fills) == 1
    assert res2.fills[0].side.value == "SELL"
    assert res2.fills[0].price == pytest.approx(1.10149)
    assert sim.position is None

    assert res2.realized_pnl == pytest.approx(146.0)
    assert sim.balance == pytest.approx(10144.0)

def test_long_increase_and_reduce():
    sim = PolicySimulator(initial_balance=10000.0, symbol="EURUSD", cost_model=TransactionCostModel(point_value=0.00001, contract_size=100000.0))
    t1 = datetime(2026,1,1, tzinfo=UTC)
    sim.process_step(ActionProposal(symbol="EURUSD", target_weight=0.5), create_mock_row(t1, 1.1000, 1.1010, spread=0.0))
    assert sim.position.volume == 0.5

    t2 = t1 + timedelta(minutes=1)
    res2 = sim.process_step(ActionProposal(symbol="EURUSD", target_weight=1.0), create_mock_row(t2, 1.1010, 1.1020, spread=0.0))
    assert len(res2.fills) == 1
    assert res2.fills[0].volume == 0.5
    assert sim.position.volume == 1.0
    assert sim.position.open_price == pytest.approx(1.1005)

    t3 = t2 + timedelta(minutes=1)
    res3 = sim.process_step(ActionProposal(symbol="EURUSD", target_weight=0.5), create_mock_row(t3, 1.1020, 1.1030, spread=0.0))
    assert len(res3.fills) == 1
    assert res3.fills[0].volume == 0.5
    assert res3.fills[0].side.value == "SELL"
    assert sim.position.volume == 0.5
    assert res3.realized_pnl == pytest.approx((1.1020 - 1.1005) * 0.5 * 100000.0)

def test_short_increase_and_reduce():
    sim = PolicySimulator(initial_balance=10000.0, symbol="EURUSD", cost_model=TransactionCostModel(point_value=0.00001, contract_size=100000.0))
    t1 = datetime(2026,1,1, tzinfo=UTC)
    sim.process_step(ActionProposal(symbol="EURUSD", target_weight=-0.5), create_mock_row(t1, 1.1000, 1.0990, spread=0.0))
    assert sim.position.volume == 0.5

    t2 = t1 + timedelta(minutes=1)
    sim.process_step(ActionProposal(symbol="EURUSD", target_weight=-1.0), create_mock_row(t2, 1.0990, 1.0980, spread=0.0))
    assert sim.position.volume == 1.0
    assert sim.position.open_price == pytest.approx(1.0995)

    t3 = t2 + timedelta(minutes=1)
    res3 = sim.process_step(ActionProposal(symbol="EURUSD", target_weight=-0.5), create_mock_row(t3, 1.0980, 1.0970, spread=0.0))
    assert res3.fills[0].side.value == "BUY"
    assert res3.realized_pnl == pytest.approx((1.0995 - 1.0980) * 0.5 * 100000.0)

def test_long_to_short_reversal():
    sim = PolicySimulator(initial_balance=10000.0, symbol="EURUSD", cost_model=TransactionCostModel(point_value=0.00001, contract_size=100000.0))
    t1 = datetime(2026,1,1, tzinfo=UTC)

    sim.process_step(ActionProposal(symbol="EURUSD", target_weight=1.0), create_mock_row(t1, 1.1000, 1.1010, spread=0.0))

    t2 = t1 + timedelta(minutes=1)
    res2 = sim.process_step(ActionProposal(symbol="EURUSD", target_weight=-1.0), create_mock_row(t2, 1.1010, 1.1020, spread=0.0))

    assert len(res2.fills) == 2
    assert res2.fills[0].side.value == "SELL"
    assert res2.fills[1].side.value == "SELL"
    assert sim.position.side.value == "SELL"
    assert sim.position.volume == 1.0
    assert res2.realized_pnl == pytest.approx(100.0)

def test_invalid_data_flattens_and_halts():
    sim = PolicySimulator(initial_balance=10000.0, symbol="EURUSD", cost_model=TransactionCostModel(point_value=0.00001, contract_size=100000.0))
    t1 = datetime(2026,1,1, tzinfo=UTC)

    sim.process_step(ActionProposal(symbol="EURUSD", target_weight=1.0), create_mock_row(t1, 1.1000, 1.1010, spread=0.0))

    t2 = t1 + timedelta(minutes=1)
    res2 = sim.process_step(ActionProposal(symbol="EURUSD", target_weight=1.0), create_mock_row(t2, 1.1010, 1.1020, spread=2.0, state=FeatureState.INVALID))

    assert res2.is_done is True
    assert sim.position is None
    assert len(res2.fills) == 1
    assert res2.realized_pnl == pytest.approx(100.0)
    # The spread used was 2.0. Selling a long uses BID (1.1010)

def test_end_of_data_behavior_long():
    sim = PolicySimulator(initial_balance=10000.0, symbol="EURUSD", cost_model=TransactionCostModel(point_value=0.00001, contract_size=100000.0))
    t1 = datetime(2026,1,1, tzinfo=UTC)
    sim.process_step(ActionProposal(symbol="EURUSD", target_weight=1.0), create_mock_row(t1, 1.1000, 1.1010, spread=2.0))

    res = sim.process_step(None, None)
    assert res.is_done is True
    assert len(res.fills) == 1
    assert res.fills[0].price == pytest.approx(1.1010) # Long flattens at BID (close price)

def test_end_of_data_behavior_short():
    sim = PolicySimulator(initial_balance=10000.0, symbol="EURUSD", cost_model=TransactionCostModel(point_value=0.00001, contract_size=100000.0))
    t1 = datetime(2026,1,1, tzinfo=UTC)
    sim.process_step(ActionProposal(symbol="EURUSD", target_weight=-1.0), create_mock_row(t1, 1.1000, 1.1010, spread=2.0))

    res = sim.process_step(None, None)
    assert res.is_done is True
    assert len(res.fills) == 1
    # Short flattens at ASK (close price + spread)
    assert res.fills[0].price == pytest.approx(1.10102)

def test_warmup_behavior():
    sim = PolicySimulator(initial_balance=10000.0, symbol="EURUSD", cost_model=TransactionCostModel())
    t1 = datetime(2026,1,1, tzinfo=UTC)

    res1 = sim.process_step(ActionProposal(symbol="EURUSD", target_weight=1.0), create_mock_row(t1, 1.1000, 1.1010, spread=0.0, state=FeatureState.WARMUP))

    assert res1.is_done is False
    assert len(res1.fills) == 0
    assert sim.position is None
    assert res1.observation is None

def test_deterministic_replay():
    sim1 = PolicySimulator(initial_balance=10000.0, symbol="EURUSD", cost_model=TransactionCostModel(point_value=0.00001, contract_size=100000.0))
    sim2 = PolicySimulator(initial_balance=10000.0, symbol="EURUSD", cost_model=TransactionCostModel(point_value=0.00001, contract_size=100000.0))

    actions = [1.0, 0.5, -0.5, -1.0, 0.0]
    prices = [1.1000, 1.1010, 1.0990, 1.0950, 1.0960]

    for i in range(5):
        t = datetime(2026,1,1, tzinfo=UTC) + timedelta(minutes=i)
        a = ActionProposal(symbol="EURUSD", target_weight=actions[i])
        r = create_mock_row(t, prices[i], prices[i]+0.0005, spread=2.0)

        res1 = sim1.process_step(a, r, next_obs_time=t + timedelta(minutes=1))
        res2 = sim2.process_step(a, r, next_obs_time=t + timedelta(minutes=1))

        assert res1.timestamp == res2.timestamp
        assert res1.realized_pnl == res2.realized_pnl
        assert res1.is_done == res2.is_done
        assert res1.portfolio.timestamp == res2.portfolio.timestamp
        assert res1.portfolio.equity == res2.portfolio.equity
        assert sim1.balance == sim2.balance
        assert len(res1.fills) == len(res2.fills)

        if res1.fills:
            f1 = res1.fills[0]
            f2 = res2.fills[0]
            assert f1.order_id == f2.order_id
            assert f1.position_id == f2.position_id
            assert f1.symbol == f2.symbol
            assert f1.side == f2.side
            assert f1.execution_role == f2.execution_role
            assert f1.volume == f2.volume
            assert f1.price == f2.price
            assert f1.timestamp == f2.timestamp
            assert f1.commission == f2.commission
            assert f1.swap == f2.swap

        if sim1.position:
            assert sim1.position.id == sim2.position.id

        assert res1.observation.timestamp == res2.observation.timestamp

def test_cost_model_validation():
    with pytest.raises(ValueError):
        TransactionCostModel(commission_per_unit=-1.0)
    with pytest.raises(ValueError):
        TransactionCostModel(slippage_points=-1.0)
    with pytest.raises(ValueError):
        PolicySimulator(initial_balance=10000.0, symbol="EURUSD", cost_model=TransactionCostModel(), max_position_units=-1.0)

def test_symbol_scope_mismatch():
    sim = PolicySimulator(initial_balance=10000.0, symbol="EURUSD", cost_model=TransactionCostModel())
    t1 = datetime(2026,1,1, tzinfo=UTC)
    with pytest.raises(ValueError, match="does not match simulator symbol"):
        sim.process_step(ActionProposal(symbol="GBPUSD", target_weight=1.0), create_mock_row(t1, 1.1000, 1.1010))

def test_timing_sequence():
    sim = PolicySimulator(initial_balance=10000.0, symbol="EURUSD", cost_model=TransactionCostModel(point_value=0.00001, contract_size=100000.0))
    t0 = datetime(2026,1,1, 10, 0, tzinfo=UTC)
    t1 = t0 + timedelta(minutes=1)
    t2 = t1 + timedelta(minutes=1)

    # bar_0 = [t0, t1). Features available at t1.
    # Action decided at t1 based on bar_0.
    act = ActionProposal(symbol="EURUSD", target_weight=1.0)

    # Execution occurs at bar_1 OPEN = t1.
    # bar_1 = [t1, t2). Features available at t2.
    row_bar1 = create_mock_row(t1, open_p=1.1000, close_p=1.1005, spread=0.0)

    res = sim.process_step(act, row_bar1, next_obs_time=t2)

    # Execution timestamp should be exactly t1
    assert len(res.fills) == 1
    assert res.fills[0].timestamp == t1
    assert res.fills[0].price == 1.1000 # bar_1 OPEN
    assert res.timestamp == t1 # Simulator step execution timestamp

    # Observation timestamp should be t2
    assert res.observation.timestamp == t2
    assert res.observation.close_price == 1.1005
    assert res.portfolio.timestamp == t2 # Portfolio is marked at the end of bar_1 (t2)

def test_zero_cost_model():
    sim = PolicySimulator(initial_balance=10000.0, symbol="EURUSD", cost_model=TransactionCostModel(point_value=0.00001, contract_size=100000.0, commission_per_unit=0.0, slippage_points=0.0))
    t1 = datetime(2026,1,1, tzinfo=UTC)

    act1 = ActionProposal(symbol="EURUSD", target_weight=1.0)
    row1 = create_mock_row(t1, 1.1000, 1.1010, spread=0.0)
    res1 = sim.process_step(act1, row1)

    assert res1.fills[0].price == 1.1000
    assert sim.balance == 10000.0

def test_invalid_while_flat():
    sim = PolicySimulator(initial_balance=10000.0, symbol="EURUSD", cost_model=TransactionCostModel(point_value=0.00001, contract_size=100000.0))
    t1 = datetime(2026,1,1, tzinfo=UTC)
    row = create_mock_row(t1, 1.1000, 1.1010, spread=0.0, state=FeatureState.INVALID)
    res = sim.process_step(ActionProposal(symbol="EURUSD", target_weight=1.0), row)
    assert res.is_done is True
    assert len(res.fills) == 0

def test_get_portfolio_state_deterministic():
    sim = PolicySimulator(initial_balance=10000.0, symbol="EURUSD", cost_model=TransactionCostModel(point_value=0.00001, contract_size=100000.0))
    t1 = datetime(2026,1,1, tzinfo=UTC)
    sim.process_step(ActionProposal(symbol="EURUSD", target_weight=1.0), create_mock_row(t1, 1.1000, 1.1010, spread=2.0), next_obs_time=t1)

    import time
    p1 = sim.get_portfolio_state(1.1010, spread=0.00002, timestamp=t1)
    time.sleep(0.01)
    p2 = sim.get_portfolio_state(1.1010, spread=0.00002, timestamp=t1)

    assert p1.timestamp == p2.timestamp
    assert p1.unrealized_pnl == p2.unrealized_pnl
    assert p1.equity == p2.equity
