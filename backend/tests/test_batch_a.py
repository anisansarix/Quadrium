from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
from app.baselines.policies import AlwaysLongPolicy, SimpleMomentumPolicy
from app.baselines.runner import BacktestRunner
from app.domain.models import FeatureState
from app.env.quadrium_env import QuadriumEnv
from app.risk.policy_risk import DeterministicRiskEngine, PolicyRiskConfig
from app.simulator.domain import MarketObservation
from app.simulator.policy_sim import PolicySimulator, TransactionCostModel


def create_dataset() -> pd.DataFrame:
    rows = []
    t = datetime(2026,1,1, 10,0, tzinfo=UTC)
    # Warmup
    rows.append({'timestamp': t, 'open': 1.1000, 'high': 1.1010, 'low': 1.0990, 'close': 1.1005, 'spread': 2.0, 'feature_state': FeatureState.WARMUP, 'ret_1': 0.0})
    # Valid rows
    t += timedelta(minutes=1)
    rows.append({'timestamp': t, 'open': 1.1005, 'high': 1.1015, 'low': 1.0995, 'close': 1.1010, 'spread': 2.0, 'feature_state': FeatureState.VALID, 'ret_1': 0.0005})
    t += timedelta(minutes=1)
    rows.append({'timestamp': t, 'open': 1.1010, 'high': 1.1020, 'low': 1.1000, 'close': 1.0990, 'spread': 2.0, 'feature_state': FeatureState.VALID, 'ret_1': -0.0018})
    # Invalid row
    t += timedelta(minutes=1)
    rows.append({'timestamp': t, 'open': 1.0990, 'high': 1.1000, 'low': 1.0980, 'close': 1.0995, 'spread': 2.0, 'feature_state': FeatureState.INVALID, 'ret_1': 0.0005})
    return pd.DataFrame(rows)

def test_gym_env_compliance():
    df = create_dataset()
    sim = PolicySimulator(10000.0, TransactionCostModel(point_value=0.00001, contract_size=100000.0), symbol="EURUSD")
    risk = DeterministicRiskEngine(PolicyRiskConfig())
    env = QuadriumEnv(df, sim, risk)
    
    assert env.action_space.shape == (1,)
    assert env.observation_space.shape == (1,) # ret_1 is the only valid feature mapped currently
    
    obs, _info = env.reset()
    assert obs.shape == (1,)
    
    # Action step
    action = np.array([1.0], dtype=np.float32)
    _obs, reward, term, _trunc, _info = env.step(action)
    
    assert isinstance(reward, float)
    assert isinstance(term, bool)
    assert isinstance(_trunc, bool)
    assert np.isfinite(_obs).all()

def test_risk_clamp_behavior():
    sim = PolicySimulator(10000.0, TransactionCostModel(point_value=0.00001, contract_size=100000.0), symbol="EURUSD")
    risk = DeterministicRiskEngine(PolicyRiskConfig(max_absolute_weight=0.5))
    df = create_dataset()
    env = QuadriumEnv(df, sim, risk)
    
    env.reset()
    # Agent tries 1.0, risk should clamp to 0.5
    _, _, _, _, info = env.step(np.array([1.0], dtype=np.float32))
    assert info['risk_decision'] == "CLAMPED_TO_MAX_WEIGHT"
    assert env.simulator.position.volume == 0.5

def test_baseline_runner_integration():
    df = create_dataset()
    sim = PolicySimulator(10000.0, TransactionCostModel(point_value=0.00001, contract_size=100000.0), symbol="EURUSD")
    risk = DeterministicRiskEngine(PolicyRiskConfig())
    env = QuadriumEnv(df, sim, risk)
    
    policy = AlwaysLongPolicy()
    runner = BacktestRunner(env, policy)
    result = runner.run()
    
    assert 'metrics' in result
    assert result['metrics']['final_equity'] > 0
    assert len(result['equity_curve']) > 0

def test_risk_rejection_disabled():
    df = create_dataset()
    sim = PolicySimulator(10000.0, TransactionCostModel(point_value=0.00001, contract_size=100000.0), symbol="EURUSD")
    risk = DeterministicRiskEngine(PolicyRiskConfig(trading_disabled=True))
    env = QuadriumEnv(df, sim, risk)
    
    env.reset()
    _, _, _, _, info = env.step(np.array([1.0], dtype=np.float32))
    assert info['risk_decision'] == "TRADING_DISABLED"
    assert env.simulator.position is None

def test_invalid_data_terminates_in_env():
    df = create_dataset()
    sim = PolicySimulator(10000.0, TransactionCostModel(point_value=0.00001, contract_size=100000.0), symbol="EURUSD")
    risk = DeterministicRiskEngine(PolicyRiskConfig())
    env = QuadriumEnv(df, sim, risk)
    
    env.reset() # Skips warmup, points to index 1
    # Step index 1 (valid)
    _obs, _rew, term, _trunc, info = env.step(np.array([1.0], dtype=np.float32))
    assert not term
    # Step index 2 (valid)
    _obs, _rew, term, _trunc, info = env.step(np.array([1.0], dtype=np.float32))
    assert not term
    # Step index 3 (invalid)
    _obs, _rew, term, _trunc, info = env.step(np.array([1.0], dtype=np.float32))
    assert term
    assert info['reason'] == "INVALID_DATA"
    assert env.simulator.position is None # Flattened securely

def test_baseline_causality():
    policy = SimpleMomentumPolicy()
    t = datetime(2026,1,1, 10,0, tzinfo=UTC)
    obs1 = MarketObservation(timestamp=t, symbol="EURUSD", features={'ret_1': 0.05}, close_price=1.1)
    act1 = policy.predict(obs1)
    assert act1.target_weight == 1.0
    
    obs2 = MarketObservation(timestamp=t, symbol="EURUSD", features={'ret_1': -0.05}, close_price=1.1)
    act2 = policy.predict(obs2)
    assert act2.target_weight == -1.0



