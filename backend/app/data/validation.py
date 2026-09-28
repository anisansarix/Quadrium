import pandas as pd
from datetime import timezone

def validate_dataframe(df: pd.DataFrame):
    if df.empty:
        return
    
    # Check UTC
    if df['timestamp'].dt.tz is None or df['timestamp'].dt.tz != timezone.utc:
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
