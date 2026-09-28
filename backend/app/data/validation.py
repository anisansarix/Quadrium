from datetime import UTC

import pandas as pd

from app.data.providers.base import DataProvider


def require_execution_capability(provider: DataProvider) -> None:
    if not provider.capabilities.suitable_for_execution_backtest:
        raise ValueError(f"Provider {provider.__class__.__name__} is not suitable for execution backtests")

def validate_dataframe(df: pd.DataFrame) -> None:
    if df.empty:
        return
    
    # Check UTC
    if df['timestamp'].dt.tz is None or df['timestamp'].dt.tz != UTC:
        raise ValueError("Timestamps must be UTC")
        
    # Monotonic
    if not df['timestamp'].is_monotonic_increasing:
        raise ValueError("Timestamps must be monotonically increasing")
        
    # Duplicates
    if df['timestamp'].duplicated().any():
        raise ValueError("Duplicate timestamps found")
        
    # Invalid OHLC
    invalid_ohlc = df[(df['high'] < df['low']) | (df['high'] < df['open']) | (df['high'] < df['close']) | (df['low'] > df['open']) | (df['low'] > df['close'])]
    if not invalid_ohlc.empty:
        raise ValueError("Invalid OHLC relationships found")
