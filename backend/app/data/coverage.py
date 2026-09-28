from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd


class DataCalendar(ABC):
    @abstractmethod
    def get_expected_bars(self, start: datetime, end: datetime, freq: str) -> list[datetime]:
        pass

class FXCalendar(DataCalendar):
    def get_expected_bars(self, start: datetime, end: datetime, freq: str) -> list[datetime]:
        expected_range = pd.date_range(start=start, end=end, freq=freq, tz='UTC', inclusive='left')
        # Filter weekends (Saturday and Sunday)
        expected_weekdays = expected_range[expected_range.dayofweek < 5]
        
        # Filter daily rollover (Friday 22:00 to Sunday 22:00 UTC)
        valid = []
        for ts in expected_weekdays:
            if ts.dayofweek == 4 and ts.hour >= 22:
                continue
            valid.append(ts)
        return valid

def evaluate_coverage(df: pd.DataFrame, requested_start: datetime, requested_end: datetime, timeframe: str, calendar: DataCalendar | None = None) -> tuple[str, list[datetime]]:
    if calendar is None:
        calendar = FXCalendar()
        
    if df.empty:
        return "EMPTY", []
        
    freq_map = {"M1": "1min", "M5": "5min"}
    if timeframe not in freq_map:
        return "PARTIAL", []
        
    expected_bars = calendar.get_expected_bars(requested_start, requested_end, freq_map[timeframe])
    if not expected_bars:
        # Request only spanned a weekend/closure
        return "FULL", []
        
    expected_start = expected_bars[0]
    expected_end = expected_bars[-1]
    
    returned_start = df['timestamp'].min()
    returned_end = df['timestamp'].max()
    
    status = "FULL"
    if returned_start > expected_start or returned_end < expected_end:
        status = "PARTIAL"
        
    return status, expected_bars
