import pytest
import pandas as pd
import numpy as np

from app.services.feature_service import FeatureService
from app.core.exceptions import DataError

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

def test_available_features():
    features = FeatureService.get_available_features()
    assert "rsi" in features
    assert "macd" in features
    assert "bollinger_bands" in features
    assert isinstance(features, list)

def test_apply_features_empty_df():
    with pytest.raises(DataError, match="Cannot apply features to an empty DataFrame"):
        FeatureService.apply_features(pd.DataFrame(), ["rsi"])

def test_apply_features_missing_cols():
    df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
    with pytest.raises(DataError, match="Missing required columns"):
        FeatureService.apply_features(df, ["rsi"])

def test_apply_features_rsi():
    df = create_sample_df(100)
    res = FeatureService.apply_features(df, ["rsi"])
    
    # 14 is default period, so first 14 might be NaN, meaning rows drop by 14
    assert len(res) < 100
    assert "RSI_14" in res.columns

def test_apply_features_multiple():
    df = create_sample_df(250)
    res = FeatureService.apply_features(df, ["rsi", "macd", "sma"])
    
    assert "RSI_14" in res.columns
    assert "MACD_12_26_9" in res.columns
    assert "SMA_20" in res.columns
    assert "SMA_50" in res.columns
    
    # Check that rows with NaN are dropped
    assert res.isna().sum().sum() == 0
