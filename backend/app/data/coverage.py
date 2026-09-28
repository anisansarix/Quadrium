from abc import ABC, abstractmethod
from datetime import datetime, time

import pandas as pd
from pydantic import BaseModel


class SessionWindow(BaseModel):
    start_day: int # 0=Monday, 6=Sunday
    start_time: time
    end_day: int
    end_time: time

class ConfigurableCalendarConfig(BaseModel):
    sessions: list[SessionWindow]
    closed_dates: list[str] = [] # e.g. "2023-12-25"

class DataCalendar(ABC):
    @abstractmethod
    def get_expected_bars(self, start: datetime, end: datetime, freq: str) -> list[datetime]:
        pass

class ConfigurableCalendar(DataCalendar):
    def __init__(self, config: ConfigurableCalendarConfig):
        self.config = config
        
    def get_expected_bars(self, start: datetime, end: datetime, freq: str) -> list[datetime]:
        expected_range = pd.date_range(start=start, end=end, freq=freq, tz='UTC', inclusive='left')
        
        valid = []
        for ts in expected_range:
            # Check closed dates
            date_str = ts.strftime('%Y-%m-%d')
            if date_str in self.config.closed_dates:
                continue
                
            # Check if within any session window
            in_session = False
            for session in self.config.sessions:
                # Basic wrap-around logic for weekly sessions
                # E.g., Sunday 22:00 to Friday 22:00
                day = ts.dayofweek
                t = ts.time()
                
                start_val = session.start_day * 24 * 3600 + session.start_time.hour * 3600 + session.start_time.minute * 60
                end_val = session.end_day * 24 * 3600 + session.end_time.hour * 3600 + session.end_time.minute * 60
                
                # If end_val < start_val (e.g., wrap around the week), we adjust
                if end_val < start_val:
                    end_val += 7 * 24 * 3600
                    
                current_val = day * 24 * 3600 + t.hour * 3600 + t.minute * 60
                
                # Check both current week and shifted week for wrap-around
                if start_val <= current_val < end_val or start_val <= current_val + 7 * 24 * 3600 < end_val:
                    in_session = True
                    break
                    
            if in_session:
                valid.append(ts)
                
        return valid

def evaluate_coverage(df: pd.DataFrame, requested_start: datetime, requested_end: datetime, timeframe: str, calendar: DataCalendar) -> tuple[str, list[datetime]]:
    if df.empty:
        return "EMPTY", []
        
    freq_map = {"M1": "1min", "M5": "5min"}
    if timeframe not in freq_map:
        return "PARTIAL", []
        
    expected_bars = calendar.get_expected_bars(requested_start, requested_end, freq_map[timeframe])
    if not expected_bars:
        # Request only spanned a weekend/closure
        return "FULL", []
        
    df_ts = set(df['timestamp'].dt.to_pydatetime()) if not df.empty else set()
    
    missing_count = sum(1 for ts in expected_bars if ts not in df_ts)
    
    status = "FULL"
    if missing_count > 0:
        status = "PARTIAL"
        
    return status, expected_bars
