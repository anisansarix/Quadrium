from datetime import UTC

import pandas as pd

from app.data.providers.base import DataProvider


def require_execution_capability(provider: DataProvider) -> None:
    if not provider.capabilities.suitable_for_execution_backtest:
        raise ValueError(f"Provider {provider.__class__.__name__} is not suitable for execution backtests")

def validate_dataframe(df: pd.DataFrame, expected_symbol: str | None = None, expected_timeframe: str | None = None) -> None:
    if df.empty:
        return
        
    cols = df.columns
    is_bars = 'open' in cols and 'high' in cols and 'low' in cols and 'close' in cols
    is_ticks = 'bid' in cols and 'ask' in cols
    
    if not is_bars and not is_ticks:
        raise ValueError("DataFrame must contain either OHLC columns or bid/ask columns")
        
    if 'timestamp' not in cols or 'symbol' not in cols:
        raise ValueError("Missing required columns: timestamp, symbol")
        
    if expected_symbol and (df['symbol'] != expected_symbol).any():
        raise ValueError("Symbol consistency check failed")
        
    if is_bars and expected_timeframe:
        if 'timeframe' not in cols:
            raise ValueError("Missing timeframe column")
        if (df['timeframe'] != expected_timeframe).any():
            raise ValueError("Timeframe consistency check failed")
            
    # Check UTC
    if df['timestamp'].dt.tz is None or df['timestamp'].dt.tz != UTC:
        raise ValueError("Timestamps must be UTC")
        
    # Monotonic
    if not df['timestamp'].is_monotonic_increasing:
        raise ValueError("Timestamps must be monotonically increasing")
        
    # Duplicates
    if df['timestamp'].duplicated().any():
        raise ValueError("Duplicate timestamps found")
        
    if is_bars:
        invalid_ohlc = df[(df['high'] < df['low']) | (df['high'] < df['open']) | (df['high'] < df['close']) | (df['low'] > df['open']) | (df['low'] > df['close'])]
        if not invalid_ohlc.empty:
            raise ValueError("Invalid OHLC relationships found")
            
        if (df['open'] <= 0).any() or (df['high'] <= 0).any() or (df['low'] <= 0).any() or (df['close'] <= 0).any():
            raise ValueError("Positive prices check failed")
            
    if is_ticks:
        if (df['bid'] <= 0).any() or (df['ask'] <= 0).any():
            raise ValueError("Positive prices check failed for ticks")
        if (df['bid'] > df['ask']).any():
            raise ValueError("bid > ask check failed")
        if 'spread' in cols and (df['spread'] < 0).any():
            raise ValueError("non-negative spread check failed")
