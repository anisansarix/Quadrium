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
    sim = PolicySimulator(initial_balance=10000.0, cost_model=TransactionCostModel(point_value=0.00001, contract_size=100000.0))
    t1 = datetime(2026,1,1, tzinfo=UTC)
    
    # Flat -> Long (Weight 1.0)
    act1 = ActionProposal(symbol="EURUSD", target_weight=1.0)
    row1 = create_mock_row(t1, 1.1000, 1.1010, spread=2.0)
    # Execution price = 1.1000 (open). Buy implies paying spread = 1.1000 + 0.00002 = 1.10002.
    res1 = sim.process_step(act1, row1)
    
    assert len(res1.fills) == 1
    assert res1.fills[0].side.value == "BUY"
    assert res1.fills[0].price == 1.10002
    assert sim.position.volume == 1.0
    
    # Portfolio equity at close (1.1010). Unrealized = (1.1010 - 1.10002) * 100000 = 98.0
    assert res1.portfolio.unrealized_pnl == pytest.approx(98.0)
    assert res1.portfolio.equity == pytest.approx(10098.0)
    
    # Long -> Flat (Weight 0.0)
    t2 = t1 + timedelta(minutes=1)
    act2 = ActionProposal(symbol="EURUSD", target_weight=0.0)
    row2 = create_mock_row(t2, 1.1015, 1.1020, spread=2.0)
    # Exec price = 1.1015 (open). Sell implies paying NO spread (assuming bid=open). So 1.1015.
    res2 = sim.process_step(act2, row2)
    
    assert len(res2.fills) == 1
    assert res2.fills[0].side.value == "SELL"
    assert res2.fills[0].price == 1.1015
    assert sim.position is None
    
    # Realized PnL = (1.1015 - 1.10002) * 100000 = 148.0
    assert res2.realized_pnl == pytest.approx(148.0)
    assert sim.balance == pytest.approx(10148.0)

def test_long_to_short_reversal():
    sim = PolicySimulator(initial_balance=10000.0, cost_model=TransactionCostModel(point_value=0.00001, contract_size=100000.0))
    t1 = datetime(2026,1,1, tzinfo=UTC)
    
    # Flat -> Long (Weight 1.0)
    sim.process_step(ActionProposal(symbol="EURUSD", target_weight=1.0), create_mock_row(t1, 1.1000, 1.1010, spread=0.0))
    # Price = 1.1000
    
    # Long -> Short (Weight -1.0)
    t2 = t1 + timedelta(minutes=1)
    res2 = sim.process_step(ActionProposal(symbol="EURUSD", target_weight=-1.0), create_mock_row(t2, 1.1010, 1.1020, spread=0.0))
    
    assert len(res2.fills) == 2 # One to flatten, one to open short
    assert res2.fills[0].side.value == "SELL" # Flatten long
    assert res2.fills[1].side.value == "SELL" # Open short
    assert sim.position.side.value == "SELL"
    assert sim.position.volume == 1.0
    
    assert res2.realized_pnl == pytest.approx(100.0)

def test_invalid_data_flattens_and_halts():
    sim = PolicySimulator(initial_balance=10000.0, cost_model=TransactionCostModel(point_value=0.00001, contract_size=100000.0))
    t1 = datetime(2026,1,1, tzinfo=UTC)
    
    # Flat -> Long
    sim.process_step(ActionProposal(symbol="EURUSD", target_weight=1.0), create_mock_row(t1, 1.1000, 1.1010, spread=0.0))
    
    # Invalid Data hits -> Should flatten unconditionally and set is_done=True
    t2 = t1 + timedelta(minutes=1)
    res2 = sim.process_step(ActionProposal(symbol="EURUSD", target_weight=1.0), create_mock_row(t2, 1.1010, 1.1020, spread=0.0, state=FeatureState.INVALID))
    
    assert res2.is_done is True
    assert sim.position is None
    assert len(res2.fills) == 1 # Flattened
    assert res2.realized_pnl == pytest.approx(100.0)

def test_deterministic_replay():
    sim1 = PolicySimulator(initial_balance=10000.0, cost_model=TransactionCostModel(point_value=0.00001, contract_size=100000.0))
    sim2 = PolicySimulator(initial_balance=10000.0, cost_model=TransactionCostModel(point_value=0.00001, contract_size=100000.0))
    
    actions = [1.0, 0.5, -0.5, -1.0, 0.0]
    prices = [1.1000, 1.1010, 1.0990, 1.0950, 1.0960]
    
    for i in range(5):
        t = datetime(2026,1,1, tzinfo=UTC) + timedelta(minutes=i)
        a = ActionProposal(symbol="EURUSD", target_weight=actions[i])
        r = create_mock_row(t, prices[i], prices[i]+0.0005, spread=2.0)
        
        res1 = sim1.process_step(a, r)
        res2 = sim2.process_step(a, r)
        
        assert res1.portfolio.equity == res2.portfolio.equity
        assert sim1.balance == sim2.balance
        assert len(res1.fills) == len(res2.fills)
