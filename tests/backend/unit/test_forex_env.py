import pytest
import numpy as np
import pandas as pd

from app.ml.environments.forex_env import QuadriumTradingEnv

def create_sample_df(rows: int = 100) -> pd.DataFrame:
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=rows, freq="h")
    return pd.DataFrame({
        "time": dates,
        "open": np.random.uniform(1.0, 1.1, rows),
        "high": np.random.uniform(1.05, 1.15, rows),
        "low": np.random.uniform(0.95, 1.05, rows),
        "close": np.random.uniform(1.0, 1.1, rows),
        "volume": np.random.randint(100, 1000, rows),
        "rsi_14": np.random.uniform(20, 80, rows)
    })

def test_quadrium_trading_env_init():
    df = create_sample_df(100)
    env = QuadriumTradingEnv(df, window_size=10)
    
    assert env.initial_balance == 10000.0
    assert env.window_size == 10
    
    obs, info = env.reset()
    # 5 features (open, high, low, close, volume, rsi_14) = 6 features
    # Window size 10 -> 60
    # +2 for account state = 62
    assert obs.shape == (62,)
    assert info["step"] == 9
    assert info["net_worth"] == 10000.0

def test_quadrium_trading_env_step():
    df = create_sample_df(100)
    env = QuadriumTradingEnv(df, window_size=10)
    env.reset()
    
    # Go long
    action = np.array([1.0], dtype=np.float32)
    obs, reward, done, truncated, info = env.step(action)
    
    assert info["step"] == 10
    assert not done
    assert "net_worth" in info
    assert info["position"] > 0
