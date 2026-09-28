import pandas as pd
from pydantic import BaseModel
from datetime import datetime

class ExpectedInterval(BaseModel):
    start: datetime
    end: datetime

class MissingInterval(BaseModel):
    start: datetime
    end: datetime
    bars_missing: int

class GapReport(BaseModel):
    expected_bars: int
    observed_bars: int
    missing_bars: int
    missing_intervals: list[MissingInterval]
    weekend_bars: int
    known_closures_bars: int

def analyze_gaps(df: pd.DataFrame, timeframe: str) -> GapReport:
    if df.empty or 'timestamp' not in df.columns:
        return GapReport(expected_bars=0, observed_bars=0, missing_bars=0, missing_intervals=[], weekend_bars=0, known_closures_bars=0)
        
    start = df['timestamp'].min()
    end = df['timestamp'].max()
    
    freq_map = {"M1": "1min", "M5": "5min"}
    if timeframe not in freq_map:
        return GapReport(expected_bars=0, observed_bars=0, missing_bars=0, missing_intervals=[], weekend_bars=0, known_closures_bars=0)
        
    freq = freq_map[timeframe]
    expected_range = pd.date_range(start=start, end=end, freq=freq, tz='UTC')
    
    # Filter weekends
    expected_weekdays = expected_range[expected_range.dayofweek < 5] # 0-4 are Mon-Fri
    
    expected_bars = len(expected_weekdays)
    observed_bars = len(df)
    
    df_ts = set(df['timestamp'])
    missing = sorted([ts for ts in expected_weekdays if ts not in df_ts])
    missing_bars = len(missing)
    
    missing_intervals = []
    if missing:
        # Group adjacent missing bars
        current_start = missing[0]
        current_prev = missing[0]
        count = 1
        delta = pd.Timedelta(freq)
        
        for ts in missing[1:]:
            if ts == current_prev + delta:
                current_prev = ts
                count += 1
            else:
                missing_intervals.append(MissingInterval(start=current_start, end=current_prev, bars_missing=count))
                current_start = ts
                current_prev = ts
                count = 1
        missing_intervals.append(MissingInterval(start=current_start, end=current_prev, bars_missing=count))
        
    return GapReport(
        expected_bars=expected_bars,
        observed_bars=observed_bars,
        missing_bars=missing_bars,
        missing_intervals=missing_intervals,
        weekend_bars=len(expected_range) - len(expected_weekdays),
        known_closures_bars=0
    )
