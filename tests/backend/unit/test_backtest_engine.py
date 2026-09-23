import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

from app.services.backtest_engine import BacktestEngine
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
        "volume": np.random.randint(100, 1000, rows)
    })

@patch("app.ml.agents.finrl_agents.AgentFactory.load_agent")
@patch("app.services.backtest_engine.get_duckdb")
def test_backtest_engine_run(mock_get_duckdb, mock_load_agent):
    df = create_sample_df(50)
    
    mock_model = MagicMock()
    # Always act "long" full size (1.0) for 10 steps, then short for 10 steps
    def side_effect_predict(obs, deterministic=True):
        if not hasattr(side_effect_predict, 'step'):
            side_effect_predict.step = 0
        side_effect_predict.step += 1
        
        if side_effect_predict.step < 10:
            return np.array([1.0]), None
        elif side_effect_predict.step < 20:
            return np.array([-1.0]), None
        else:
            return np.array([0.0]), None

    mock_model.predict.side_effect = side_effect_predict
    mock_load_agent.return_value = mock_model
    
    mock_conn = MagicMock()
    mock_get_duckdb.return_value = mock_conn

    engine = BacktestEngine(
        experiment_id="exp_1",
        df=df,
        agent_type="ppo",
        model_path="dummy_path",
        instrument="XAUUSD"
    )
    
    backtest_id = engine.run()
    
    assert backtest_id is not None
    # We should have some trades since we flip from long to short to flat
    assert len(engine.trades) > 0
    assert len(engine.equity_curve) > 0
    
    # Check DB was called
    assert mock_conn.executemany.called or mock_conn.execute.called
