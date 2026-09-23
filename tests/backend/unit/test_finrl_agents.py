import pytest
import pandas as pd
from unittest.mock import MagicMock

from app.ml.agents.finrl_agents import AgentFactory
from app.ml.environments.forex_env import QuadriumTradingEnv

def create_sample_df(rows: int = 100) -> pd.DataFrame:
    import numpy as np
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=rows, freq="h")
    return pd.DataFrame({
        "time": dates,
        "open": np.random.uniform(1.0, 1.1, rows),
        "high": np.random.uniform(1.05, 1.15, rows),
        "low": np.random.uniform(0.95, 1.05, rows),
        "close": np.random.uniform(1.0, 1.1, rows),
        "volume": np.random.randint(100, 1000, rows)
    })

def test_create_ppo_agent():
    df = create_sample_df(50)
    env = QuadriumTradingEnv(df)
    
    agent = AgentFactory.create_agent("ppo", env)
    assert agent is not None
    # Check if it has correct class name
    assert agent.__class__.__name__ == "PPO"

def test_unsupported_agent():
    df = create_sample_df(10)
    env = QuadriumTradingEnv(df, window_size=5)
    
    with pytest.raises(Exception, match="Unsupported agent type"):
        AgentFactory.create_agent("unknown", env)
