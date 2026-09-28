from datetime import datetime

import pandas as pd
from pydantic import BaseModel

from app.data.coverage import DataCalendar, FXCalendar


class MissingInterval(BaseModel):
    start: datetime
    end: datetime
    bars_missing: int
    is_known_closure: bool

class GapReport(BaseModel):
    expected_bars: int
    observed_bars: int
    missing_bars: int
    missing_intervals: list[MissingInterval]
    weekend_bars: int
    known_closures_bars: int
    unexpected_missing_bars: int

def analyze_gaps(df: pd.DataFrame, timeframe: str, start: datetime, end: datetime, calendar: DataCalendar | None = None) -> GapReport:
    if calendar is None:
        calendar = FXCalendar()
        
    freq_map = {"M1": "1min", "M5": "5min"}
    if timeframe not in freq_map:
        return GapReport(expected_bars=0, observed_bars=0, missing_bars=0, missing_intervals=[], weekend_bars=0, known_closures_bars=0, unexpected_missing_bars=0)
        
    freq = freq_map[timeframe]
    expected_range = pd.date_range(start=start, end=end, freq=freq, tz='UTC', inclusive='left')
    expected_weekdays = calendar.get_expected_bars(start, end, freq)
    
    expected_bars_count = len(expected_weekdays)
    observed_bars = len(df)
    
    df_ts = set(df['timestamp']) if not df.empty and 'timestamp' in df.columns else set()
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
                missing_intervals.append(MissingInterval(start=current_start, end=current_prev, bars_missing=count, is_known_closure=False))
                current_start = ts
                current_prev = ts
                count = 1
        missing_intervals.append(MissingInterval(start=current_start, end=current_prev, bars_missing=count, is_known_closure=False))
        
    return GapReport(
        expected_bars=expected_bars_count,
        observed_bars=observed_bars,
        missing_bars=missing_bars,
        missing_intervals=missing_intervals,
        weekend_bars=len(expected_range) - expected_bars_count,
        known_closures_bars=0,
        unexpected_missing_bars=missing_bars
    )
